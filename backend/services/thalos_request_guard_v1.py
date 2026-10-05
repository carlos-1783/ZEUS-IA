"""THALOS J5 — guard de entrada por peticion y auditoria post-accion (cadena JARVIS, paso 6).

Reutiliza el sistema de eventos EXISTENTE de THALOS (`ThalosSecurityEvent` via
`thalos_security_engine._persist_event`) y `ActivityLogger` (agent_activities). No crea
tablas ni un segundo sistema de eventos.

Funciona con los flags por defecto: NO depende de THALOS_REAL_MONITORING ni de
ZEUS_CORE_GUARD_ENFORCE. Con esos flags activos, ademas actuan (sin cambios aqui) el
`ThalosLoginAuditMiddleware` (login) y `validate_critical_action` en modo enforce (executor).

1. `thalos_request_guard` (dependencia FastAPI):
   - valida la entrada: tamano de cuerpo, longitud del mensaje, tamano del context,
     caracteres de control (NUL y C0 salvo \\t \\n \\r). La "sanitizacion" es rechazo
     explicito (4xx): el cuerpo ya esta parseado por FastAPI cuando se evalua la
     dependencia, y alterar el texto cambiaria su significado.
   - usuario activo (estado real de bloqueo: `block_user`/`secure_deactivate` ponen
     is_active=False) y empresa resuelta en servidor; el superusuario puede no tener empresa.
   - registra SIEMPRE un evento THALOS (allow/deny, tenant, usuario, ruta, motivo).
2. `thalos_audit_result`: verifica tras ejecutar (tenant del resultado, no simulado,
   success/executed reales) y registra evento THALOS + agent_activities. Fail-closed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256 * 1024
# Cuerpos NO JSON (multipart/ficheros): no se parsean ni se leen en memoria desde el guard;
# solo se limita el tamano declarado (Content-Length). Ninguna ruta guardada recibe hoy ficheros.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_MESSAGE_CHARS = 8000
MAX_CONTEXT_JSON_CHARS = 20000
_TEXT_FIELDS = ("message", "task_description")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_DEPTH = 20

_table_checked = False


def _ensure_table() -> None:
    """Idempotente: en prod la crea Alembic; en entornos locales evita fallar por tabla ausente."""
    global _table_checked
    if _table_checked:
        return
    try:
        from app.db.base import engine
        from app.models.thalos_security_event import ThalosSecurityEvent

        ThalosSecurityEvent.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        logger.exception("THALOS: no se pudo comprobar thalos_security_events")
    _table_checked = True


def record_security_event(
    db: Session,
    *,
    event_type: str,
    severity: str,
    source: str,
    details: Dict[str, Any],
    user: Optional[User] = None,
    company_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    action_taken: Optional[str] = None,
    decision_rule: Optional[str] = None,
) -> bool:
    """Persiste un ThalosSecurityEvent (commit propio). True si quedo registrado."""
    from services import thalos_security_engine

    _ensure_table()
    try:
        thalos_security_engine._persist_event(
            db,
            event_type=event_type,
            severity=severity,
            source=source,
            details=details,
            user_id=getattr(user, "id", None),
            user_email=getattr(user, "email", None),
            ip_address=ip_address,
            company_id=company_id,
            action_taken=action_taken,
            decision_rule=decision_rule,
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception("THALOS: no se pudo registrar el evento %s", event_type)
        return False


# --------------------------------------------------------------------- entrada


def _walk_strings(node: Any, depth: int = 0):
    if depth > _MAX_DEPTH:
        raise ValueError("estructura demasiado profunda")
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str):
                yield k
            yield from _walk_strings(v, depth + 1)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _walk_strings(v, depth + 1)


def validate_request_body(raw: bytes) -> Optional[tuple]:
    """None si es valido; (http_status, motivo) si se rechaza."""
    if len(raw) > MAX_BODY_BYTES:
        return 413, "body_too_large"
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return 400, "invalid_json"
    if not isinstance(data, dict):
        return None
    for f in _TEXT_FIELDS:
        v = data.get(f)
        if isinstance(v, str) and len(v) > MAX_MESSAGE_CHARS:
            return 413, f"{f}_too_long"
    ctx = data.get("context")
    if ctx is not None:
        try:
            if len(json.dumps(ctx, ensure_ascii=False, default=str)) > MAX_CONTEXT_JSON_CHARS:
                return 413, "context_too_large"
        except (TypeError, ValueError):
            return 400, "context_invalid"
    try:
        for s in _walk_strings(data):
            if _CONTROL_RE.search(s):
                return 400, "control_characters"
    except ValueError:
        return 400, "payload_too_deep"
    return None


_DENY_DETAIL = {
    "body_too_large": "Peticion demasiado grande.",
    "message_too_long": "El mensaje supera la longitud maxima permitida.",
    "task_description_too_long": "La descripcion supera la longitud maxima permitida.",
    "context_too_large": "El contexto supera el tamano maximo permitido.",
    "context_invalid": "Contexto no valido.",
    "invalid_json": "Cuerpo de la peticion no valido.",
    "control_characters": "La peticion contiene caracteres de control no permitidos.",
    "payload_too_deep": "Estructura de la peticion demasiado profunda.",
    "user_inactive": "Usuario bloqueado o inactivo.",
    "no_company": "El usuario no tiene empresa asignada.",
}


def _client_ip(request: Request) -> Optional[str]:
    try:
        from app.core.security_middleware import get_real_client_ip

        return get_real_client_ip(request)
    except Exception:
        return request.client.host if request.client else None


def _body_verdict_sync_meta(request: Request) -> Optional[tuple]:
    """Veredicto para cuerpos NO JSON (solo Content-Length declarado).

    None si el cuerpo es JSON/sin tipo (hay que validarlo); (0, "") si es no-JSON valido."""
    ctype = (request.headers.get("content-type") or "").lower()
    if ctype and "json" not in ctype:
        try:
            declared = int(request.headers.get("content-length") or 0)
        except ValueError:
            declared = MAX_UPLOAD_BYTES + 1
        return (413, "body_too_large") if declared > MAX_UPLOAD_BYTES else (0, "")
    return None


async def _incoming_verdict(request: Request) -> Optional[tuple]:
    """(status, motivo) si la entrada se rechaza; None si es valida (reutiliza validate_request_body)."""
    meta = _body_verdict_sync_meta(request)
    if meta is not None:
        return meta if meta[0] else None
    return validate_request_body(await request.body())


async def _run_request_guard(
    request: Request, current_user: User, db: Session, *, require_company: bool
) -> User:
    import services.crm_office_service as crm_svc

    route = request.scope.get("route")
    route_path = getattr(route, "path", None) or request.url.path
    ip = _client_ip(request)

    company_id: Optional[int] = None
    reason: Optional[str] = None
    code = status.HTTP_403_FORBIDDEN

    if not getattr(current_user, "is_active", True):
        reason = "user_inactive"
    else:
        try:
            company_id = crm_svc.primary_company_id(db, current_user)
        except Exception:
            logger.exception("THALOS guard: fallo resolviendo empresa")
            company_id = None
        if require_company and company_id is None and not getattr(current_user, "is_superuser", False):
            reason = "no_company"

    if reason is None:
        verdict = await _incoming_verdict(request)
        if verdict:
            code, reason = verdict

    decision = "deny" if reason else "allow"
    record_security_event(
        db,
        event_type="request_guard",
        severity="warning" if reason else "info",
        source="thalos_request_guard",
        details={
            "route": route_path,
            "method": request.method,
            "decision": decision,
            "reason": reason or "ok",
            "superuser": bool(getattr(current_user, "is_superuser", False)),
            "company_required": require_company,
        },
        user=current_user,
        company_id=company_id,
        ip_address=ip,
        action_taken=decision,
        decision_rule=reason or "request_validated",
    )
    if reason:
        raise HTTPException(status_code=code, detail=_DENY_DETAIL.get(reason, "Peticion rechazada por THALOS."))
    return current_user


async def thalos_request_guard(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependencia THALOS por peticion. Devuelve el usuario si se permite; 4xx si se deniega."""
    return await _run_request_guard(request, current_user, db, require_company=True)


async def thalos_request_guard_no_company(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Igual que `thalos_request_guard` pero sin exigir empresa (flujos previos a tener empresa)."""
    return await _run_request_guard(request, current_user, db, require_company=False)


async def _best_effort_user(request: Request, db: Session) -> Optional[User]:
    """Usuario del token si viene uno valido; nunca falla (rutas anonimas)."""
    if not request.headers.get("authorization"):
        return None
    try:
        from app.core.auth import get_current_user

        user = await get_current_user(request=request, db=db)
        return user if getattr(user, "is_active", True) else None
    except Exception:
        return None


async def _run_anonymous_guard(request: Request, db: Session, *, validate_body: bool) -> None:
    import services.crm_office_service as crm_svc

    route = request.scope.get("route")
    route_path = getattr(route, "path", None) or request.url.path
    user = await _best_effort_user(request, db)
    company_id: Optional[int] = None
    if user is not None:
        try:
            company_id = crm_svc.primary_company_id(db, user)
        except Exception:
            company_id = None

    reason: Optional[str] = None
    code = status.HTTP_400_BAD_REQUEST
    if validate_body:
        verdict = await _incoming_verdict(request)
        if verdict:
            code, reason = verdict
    decision = "deny" if reason else "allow"
    record_security_event(
        db,
        event_type="request_guard",
        severity="warning" if reason else "info",
        source="thalos_anonymous_guard",
        details={
            "route": route_path,
            "method": request.method,
            "decision": decision,
            "reason": reason or "ok",
            "anonymous": user is None,
            "body_validated": validate_body,
        },
        user=user,
        company_id=company_id,
        ip_address=_client_ip(request),
        action_taken=decision,
        decision_rule=reason or "anonymous_route_allowlisted",
    )
    if reason:
        raise HTTPException(status_code=code, detail=_DENY_DETAIL.get(reason, "Peticion rechazada por THALOS."))


async def thalos_anonymous_guard(request: Request, db: Session = Depends(get_db)) -> None:
    """Guard para rutas publicas de la allowlist: valida cuerpo y registra evento, sin exigir usuario."""
    await _run_anonymous_guard(request, db, validate_body=True)


async def thalos_anonymous_event_only_guard(request: Request, db: Session = Depends(get_db)) -> None:
    """Webhooks firmados por proveedor: SOLO evento. El cuerpo no se lee ni se valida aqui para que
    llegue intacto a la verificacion de firma del handler."""
    await _run_anonymous_guard(request, db, validate_body=False)


# ------------------------------------------------------------- cobertura global

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Rutas publicas / con otra autenticacion. Guard ANONIMO con validacion de cuerpo + evento.
ANON_BODY_ROUTES = frozenset(
    {
        "/api/v1/auth/login",  # credenciales
        "/api/v1/auth/token",  # OAuth2 form (no JSON: solo tope de tamano)
        "/api/v1/auth/register",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/new-password",
        "/api/v1/auth/refresh",  # refresh token en cuerpo, sin access token
        "/api/v1/auth/logout",  # recibe refresh token; tolera access token caducado
        "/api/v1/integrations/stripe/checkout/payment-intent",  # publica por diseno (checkout)
        "/api/v1/onboarding/create-account",  # post-pago, verifica PaymentIntent contra Stripe
        "/api/v1/p/{slug}/reservations",  # web publica por cliente
        "/api/v1/afrodita/ops/v1/routes/simulate",  # stub 410 sin auth ni cuerpo
    }
)
# Webhooks firmados por el proveedor: solo evento (cuerpo intacto para verificar firma).
ANON_EVENT_ONLY_ROUTES = frozenset(
    {
        "/api/v1/integrations/stripe/webhook",
        "/api/v1/integrations/whatsapp/webhook",
        "/api/v1/integrations/email/webhook",
        "/api/v1/webhooks/stripe",
        "/api/v1/webhooks/twilio",
    }
)
# Autenticadas pero legitimas SIN empresa (onboarding previo a empresa, ajustes de usuario).
AUTH_NO_COMPANY_ROUTES = frozenset(
    {
        "/api/v1/auth/onboarding/questionnaire",  # crea/vincula la primera empresa
        "/api/v1/auth/onboarding/profile",
        "/api/v1/onboarding/complete-onboarding",  # legacy 410, autenticada, previa a empresa
        "/api/v1/auth/debug/verify-token",  # diagnostico de token
        "/api/v1/settings",  # preferencias de usuario (PATCH)
    }
)

_GUARD_CALLS = (
    thalos_request_guard,
    thalos_request_guard_no_company,
    thalos_anonymous_guard,
    thalos_anonymous_event_only_guard,
)


def _dependant_has_guard(dependant: Any) -> bool:
    for sub in getattr(dependant, "dependencies", []) or []:
        if sub.call in _GUARD_CALLS or _dependant_has_guard(sub):
            return True
    return False


def route_is_thalos_covered(route: Any) -> bool:
    return _dependant_has_guard(route.dependant)


def _global_dependency_for(path: str):
    if path in ANON_EVENT_ONLY_ROUTES:
        return thalos_anonymous_event_only_guard
    if path in ANON_BODY_ROUTES:
        return thalos_anonymous_guard
    if path in AUTH_NO_COMPANY_ROUTES:
        return thalos_request_guard_no_company
    return thalos_request_guard


def install_global_thalos_guard(app: Any, *, prefixes: tuple = ("/api/",)) -> int:
    """Inyecta, de forma estructural, el guard THALOS en toda ruta mutante bajo `prefixes` que
    aun no lo tenga (la dependencia de ruta ya existente cuenta como cobertura: no hay doble
    evento). Reutiliza las mismas dependencias (compatible con dependency_overrides).
    Idempotente. Devuelve cuantas rutas se han cubierto."""
    from fastapi import params
    from fastapi.dependencies.utils import get_parameterless_sub_dependant
    from fastapi.routing import APIRoute

    added = 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path_format.startswith(prefixes):
            continue
        if not (set(route.methods or ()) & MUTATING_METHODS) or route_is_thalos_covered(route):
            continue
        dep = params.Depends(_global_dependency_for(route.path_format))
        route.dependencies.insert(0, dep)
        route.dependant.dependencies.insert(
            0, get_parameterless_sub_dependant(depends=dep, path=route.path_format)
        )
        added += 1
    return added


# ----------------------------------------------------------------- post-accion


def _result_company_ids(result: Dict[str, Any]):
    found = []
    for src in (result, result.get("data"), result.get("execution"), result.get("metrics")):
        if isinstance(src, dict) and src.get("company_id") is not None:
            found.append(src["company_id"])
    return found


def thalos_audit_result(
    db: Session,
    *,
    user: User,
    company_id: Optional[int],
    agent: str,
    action: str,
    result: Any,
    approval_id: Optional[int] = None,
    source: str = "thalos_audit_result",
) -> Dict[str, Any]:
    """Audita el resultado de una accion ya ejecutada. Devuelve {"ok": bool, "reason": str}.

    Falla si: el tenant esperado no coincide con la empresa del usuario o con la del
    resultado; el resultado es simulado/bloqueado; success/executed no son reales; o el
    propio registro de auditoria no puede persistirse (fail-closed)."""
    from services.zeus_core_guard_v1 import SIMULATED_HANDLER_ACTIONS
    import services.crm_office_service as crm_svc

    reason: Optional[str] = None
    res = result if isinstance(result, dict) else {}
    try:
        user_company = crm_svc.primary_company_id(db, user)
    except Exception:
        user_company = None
    expected = user_company if user_company is not None else (company_id if getattr(user, "is_superuser", False) else None)

    if expected is None or company_id is None:
        reason = "tenant_unresolved"
    elif company_id != expected:
        reason = "tenant_mismatch_user"
    elif any(c != company_id for c in _result_company_ids(res)):
        reason = "tenant_mismatch_result"
    elif res.get("execution_mode") in ("simulated", "blocked") or (action or "").lower() in SIMULATED_HANDLER_ACTIONS:
        reason = "simulated_or_blocked"
    elif not res:
        reason = "empty_result"
    elif not (res.get("success") and res.get("executed")):
        reason = "not_executed"

    ok = reason is None
    details = {
        "agent": agent,
        "action": action,
        "approval_id": approval_id,
        "verdict": "pass" if ok else "fail",
        "reason": reason or "ok",
    }
    recorded = record_security_event(
        db,
        event_type="post_action_audit",
        severity="info" if ok else "critical" if (reason or "").startswith("tenant") else "warning",
        source=source,
        details=details,
        user=user,
        company_id=company_id,
        action_taken="audit_pass" if ok else "audit_fail",
        decision_rule=reason or "result_verified",
    )
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="THALOS",
            action_type="thalos_audit_result",
            action_description=f"Auditoria THALOS de {agent}.{action}: {'OK' if ok else 'FALLIDA (' + str(reason) + ')'}",
            details=details,
            user_email=getattr(user, "email", None),
            status="completed" if ok else "failed",
            priority="normal" if ok else "high",
            company_id=company_id,
        )
    except Exception:
        logger.exception("THALOS: no se pudo registrar agent_activity de auditoria")
    if not recorded:
        return {"ok": False, "reason": "audit_unavailable"}
    return {"ok": ok, "reason": reason or "ok"}
