"""J10: RESPONDER con evidencia y CONTINUAR (JARVIS).

Contrato `evidence` (lista en `ChatResponse`): cada elemento enlaza al recurso real que respalda la
respuesta, nunca incrusta el entregable en el chat:

    {kind: document|approval|invoice|movement|route|customer|audit|activity,
     id, agent, title, url, status}

`url` es el endpoint del recurso (`GET /api/v1/jarvis/evidence/{kind}/{id}`): exige sesion, pasa por
THALOS y SOLO devuelve el recurso si pertenece a la empresa del usuario (404 en otro caso; no se revela
si existe en otra empresa). Nunca es un fichero publico.

Toda evidencia se construye releyendo el recurso con filtro de empresa (`load_resource`): un id de otra
empresa no puede aparecer en una respuesta aunque un handler lo devolviera por error.

`next_step` (CONTINUAR): propuesta concreta derivada del estado real o None.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

EVIDENCE_BASE = "/api/v1/jarvis/evidence"
KINDS = ("document", "approval", "invoice", "movement", "route", "customer", "audit", "activity")
# Respuesta de agente a partir de la cual se considera un entregable: el chat lleva un resumen corto
# y el texto completo vive en el workspace (los mensajes cortos se contestan en el propio chat).
LONG_MESSAGE_CHARS = 700
SHORT_SUMMARY_CHARS = 280
_CORRELATION_RE = re.compile(r"^[0-9a-f]{32}$")

_APPROVAL_LABEL = {
    "send_campaign": "Envío de campaña",
    "create_customer": "Alta de cliente",
    "create_ops_route": "Ruta operativa",
    "create_inventory_movement": "Movimiento de inventario",
}
_CONFIRM_VERB = {
    "send_campaign": "enviarla",
    "create_customer": "crear el cliente",
    "create_ops_route": "crear la ruta",
    "create_inventory_movement": "registrar el movimiento",
}


def url_for(kind: str, item_id: Any) -> str:
    return f"{EVIDENCE_BASE}/{kind}/{item_id}"


def make(kind: str, item_id: Any, agent: str, title: str, status: str) -> Dict[str, Any]:
    return {
        "kind": kind, "id": item_id, "agent": agent, "title": (title or "")[:200],
        "url": url_for(kind, item_id), "status": status,
    }


def _agent_label(name: Optional[str]) -> str:
    n = (name or "").upper().strip()
    return "ZEUS CORE" if n in ("ZEUS", "ZEUS CORE", "") else n


def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for it in items:
        key = (it.get("kind"), str(it.get("id")))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


# --------------------------------------------------------------------------- lectura con empresa
def load_resource(
    db: Session, user: Any, company_id: Optional[int], kind: str, item_id: str
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """-> (evidencia, detalle) o None. SIEMPRE filtra por `company_id` (la del usuario autenticado).
    Sin empresa no se devuelve nada."""
    if company_id is None or kind not in KINDS:
        return None
    try:
        if kind == "audit":
            return _load_audit(db, user, company_id, str(item_id))
        iid = int(item_id)
    except (TypeError, ValueError):
        return None
    if iid <= 0:
        return None
    loader = _LOADERS[kind]
    return loader(db, company_id, iid)


def _iso(v: Any) -> Optional[str]:
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else None


def _load_document(db: Session, cid: int, iid: int):
    from app.models.document_approval import DocumentApproval

    row = db.query(DocumentApproval).filter(DocumentApproval.id == iid, DocumentApproval.company_id == cid).first()
    if row is None:
        return None
    payload = row.document_payload if isinstance(row.document_payload, dict) else {}
    title = str(payload.get("title") or row.document_type or f"Documento {row.id}")
    ev = make("document", row.id, _agent_label(row.agent_name), title, str(row.status or "draft"))
    return ev, {"document_type": row.document_type, "payload": payload, "created_at": _iso(row.created_at)}


def _load_approval(db: Session, cid: int, iid: int):
    from app.models.zeus_pending_approval import ZeusPendingApproval

    row = (
        db.query(ZeusPendingApproval)
        .filter(ZeusPendingApproval.id == iid, ZeusPendingApproval.company_id == cid)
        .first()
    )
    if row is None:
        return None
    result_message = None
    try:
        out = json.loads(row.result_json) if row.result_json else {}
        if isinstance(out, dict):
            res = out.get("result") if isinstance(out.get("result"), dict) else {}
            result_message = res.get("message") or out.get("error")
    except (TypeError, ValueError):
        result_message = None
    title = _APPROVAL_LABEL.get(row.action_type, f"Acción {row.action_type}")
    ev = make("approval", row.id, _agent_label(row.agent_name), f"Aprobación: {title}", str(row.status))
    return ev, {
        "action_type": row.action_type, "created_at": _iso(row.created_at), "expires_at": _iso(row.expires_at),
        "executed_at": _iso(row.executed_at), "result_message": result_message,
    }


def _load_customer(db: Session, cid: int, iid: int):
    from app.models.customer import Customer

    row = db.query(Customer).filter(Customer.id == iid, Customer.company_id == cid).first()
    if row is None:
        return None
    ev = make("customer", row.id, "ZEUS CORE", f"Cliente {row.name}", "active")
    return ev, {"name": row.name, "email": row.email, "phone": row.phone}


def _load_route(db: Session, cid: int, iid: int):
    from app.models.ops_route import OpsRoute

    row = db.query(OpsRoute).filter(OpsRoute.id == iid, OpsRoute.company_id == cid).first()
    if row is None:
        return None
    ev = make("route", row.id, "AFRODITA", f"Ruta {row.origin} → {row.destination}", "created")
    return ev, {"origin": row.origin, "destination": row.destination, "distance_km": row.distance,
                "created_at": _iso(row.created_at)}


def _load_movement(db: Session, cid: int, iid: int):
    from app.models.erp import InventoryMovement, Product

    row = (
        db.query(InventoryMovement, Product)
        .join(Product, Product.id == InventoryMovement.product_id)
        .filter(InventoryMovement.id == iid, Product.company_id == cid)
        .first()
    )
    if row is None:
        return None
    mov, prod = row
    mtype = getattr(mov.movement_type, "value", mov.movement_type)
    ev = make("movement", mov.id, "AFRODITA", f"Movimiento de inventario: {prod.name}", "registered")
    return ev, {"product": prod.name, "movement_type": mtype, "quantity": mov.quantity,
                "reference": mov.reference, "created_at": _iso(mov.created_at)}


def _load_invoice(db: Session, cid: int, iid: int):
    from app.models.erp import Invoice

    row = db.query(Invoice).filter(Invoice.id == iid, Invoice.company_id == cid).first()
    if row is None:
        return None
    status = str(getattr(row.status, "value", row.status) or "draft")
    ev = make("invoice", row.id, "RAFAEL", f"Factura {row.invoice_number}", status)
    return ev, {"invoice_number": row.invoice_number, "total": row.total, "issue_date": _iso(row.issue_date)}


def _load_activity(db: Session, cid: int, iid: int):
    from app.models.agent_activity import AgentActivity

    row = db.query(AgentActivity).filter(AgentActivity.id == iid, AgentActivity.company_id == cid).first()
    if row is None:
        return None
    ev = make("activity", row.id, _agent_label(row.agent_name), row.action_description or row.action_type,
              str(row.status or "completed"))
    return ev, {"action_type": row.action_type, "created_at": _iso(row.created_at)}


def _load_audit(db: Session, user: Any, cid: int, request_id: str):
    """Registro J7 de UNA peticion del propio usuario en su empresa. Solo pasos (sin contenidos)."""
    from app.models.agent_activity import AgentActivity

    if not _CORRELATION_RE.match(request_id or ""):
        return None
    rows = (
        db.query(AgentActivity)
        .filter(AgentActivity.company_id == cid, AgentActivity.user_email == getattr(user, "email", None))
        .order_by(AgentActivity.id.desc())
        .limit(500)
        .all()
    )
    mine = [r for r in rows if (r.details or {}).get("correlation_id") == request_id]
    if not mine:
        return None
    mine.sort(key=lambda r: r.id)
    steps = [
        {"step": (r.details or {}).get("chain_step"), "action": (r.details or {}).get("action"),
         "agent": r.agent_name, "status": r.status, "at": _iso(r.created_at)}
        for r in mine
    ]
    ev = make("audit", request_id, "ZEUS CORE", "Registro de la petición", "logged")
    return ev, {"steps": steps}


_LOADERS = {
    "document": _load_document, "approval": _load_approval, "customer": _load_customer,
    "route": _load_route, "movement": _load_movement, "invoice": _load_invoice, "activity": _load_activity,
}


def evidence_item(db: Session, user: Any, company_id: Optional[int], kind: str, item_id: Any) -> Optional[Dict[str, Any]]:
    """Evidencia verificada: solo si el recurso existe EN la empresa del usuario."""
    try:
        res = load_resource(db, user, company_id, kind, str(item_id))
    except Exception:
        logger.exception("jarvis_evidence: no se pudo verificar %s/%s", kind, item_id)
        return None
    return res[0] if res else None


# --------------------------------------------------------------------------- borradores y recursos
def persist_draft_evidence(db: Session, user: Any, company_id: Optional[int], agent: str, text: str) -> Optional[Dict[str, Any]]:
    """Persiste el borrador de un paso como DocumentApproval draft del agente responsable y devuelve su
    evidencia. Si falla, deja constancia (log + aviso de la cadena J7) y devuelve None: el texto no se pierde."""
    try:
        from services.workspace_deliverables import persist_agent_chat_deliverable

        doc = persist_agent_chat_deliverable(db, user, agent, text)
        if doc is None:
            return None
        return evidence_item(db, user, company_id, "document", doc.id)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("jarvis_evidence: no se pudo guardar el borrador de %s en el workspace", agent)
        try:
            from services.chain_log import current_chain

            ctx = current_chain()
            if ctx is not None:
                ctx.warnings.append(f"No se pudo guardar el borrador de {agent} en el workspace.")
        except Exception:
            pass
        return None


def resources_from_execution(
    db: Session, user: Any, company_id: Optional[int], execution: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Recursos creados por una accion confirmada (cliente, ruta, movimiento, factura), leidos de BD con
    filtro de empresa a partir de los ids que devolvio el ejecutor."""
    if not isinstance(execution, dict):
        return []
    metrics = execution.get("metrics") if isinstance(execution.get("metrics"), dict) else {}
    data = execution.get("data") if isinstance(execution.get("data"), dict) else {}
    cand: List[Tuple[str, Any]] = []
    if metrics.get("customer_id"):
        cand.append(("customer", metrics["customer_id"]))
    route = data.get("route") if isinstance(data.get("route"), dict) else {}
    if route.get("id"):
        cand.append(("route", route["id"]))
    mov = data.get("movement") if isinstance(data.get("movement"), dict) else {}
    if mov.get("id"):
        cand.append(("movement", mov["id"]))
    inv = data.get("invoice") if isinstance(data.get("invoice"), dict) else {}
    inv_id = data.get("invoice_id") or inv.get("id") or metrics.get("invoice_id")
    if inv_id:
        cand.append(("invoice", inv_id))
    out = []
    for kind, rid in cand:
        it = evidence_item(db, user, company_id, kind, rid)
        if it is not None:
            out.append(it)
    return out


def bridge_evidence(db: Session, user: Any, company_id: Optional[int], bridge: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evidencia de una respuesta ZEUS: la que ya traiga el plan (borradores) + aprobacion + recursos."""
    items: List[Dict[str, Any]] = []
    for it in bridge.get("evidence") or []:
        # el plan ya la verifico, pero se relee: un id/url que no sea de esta empresa no sale nunca
        v = evidence_item(db, user, company_id, it.get("kind"), it.get("id"))
        if v is not None:
            items.append(v)
    if bridge.get("approval_id"):
        v = evidence_item(db, user, company_id, "approval", bridge["approval_id"])
        if v is not None:
            items.append(v)
    if bridge.get("executed"):
        items.extend(resources_from_execution(db, user, company_id, bridge.get("execution")))
    return dedupe(items)


# --------------------------------------------------------------------------- mensaje breve
def brief(text: str, agent: str) -> str:
    """Resumen de 1-3 frases + referencia al workspace (el enlace va en `evidence`)."""
    t = " ".join(str(text or "").split())
    if len(t) > SHORT_SUMMARY_CHARS:
        cut = t[:SHORT_SUMMARY_CHARS]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        t = (cut[: end + 1] if end >= 80 else cut.rsplit(" ", 1)[0].rstrip(".,;:") + "…")
    return f"{t}\n\nVer en el workspace de {agent}."


def is_long_deliverable(text: str) -> bool:
    return len((text or "").strip()) > LONG_MESSAGE_CHARS


# --------------------------------------------------------------------------- CONTINUAR
def next_step(
    db: Session, user: Any, company_id: Optional[int], bridge: Dict[str, Any], evidence: List[Dict[str, Any]]
) -> Tuple[Optional[str], Optional[str]]:
    """-> (tipo, texto) del siguiente paso logico segun el estado real, o (None, None). Solo propone
    acciones que existen (confirmar/cancelar, preparar un envio, revisar un borrador, consultar stock)."""
    if bridge.get("needs_confirmation") and bridge.get("approval_id"):
        action_type = _approval_action_type(db, company_id, bridge["approval_id"])
        verb = _CONFIRM_VERB.get(action_type or "", "ejecutarla")
        return "confirm_pending", f"Responde «confirmar» para {verb} o «cancelar» para descartarla."
    if bridge.get("needs_clarification"):
        return None, None  # la propia pregunta de ZEUS es el siguiente paso
    if bridge.get("executed"):
        kinds = {e["kind"] for e in evidence}
        if "customer" in kinds:
            return (
                "offer_after_customer",
                "¿Quieres enviarle la oferta activa? Dime «envía la oferta» y te pediré confirmación antes de enviar nada.",
            )
        if "movement" in kinds:
            return "check_inventory", "Si quieres, consulto el estado del inventario para ver el stock actualizado."
        return None, None
    drafts = [e for e in evidence if e["kind"] == "document" and e.get("status") in ("draft", "pending_approval")]
    if drafts:
        return "review_draft", f"Revisa el borrador en el workspace de {drafts[0]['agent']} y apruébalo."
    return None, None


def _approval_action_type(db: Session, company_id: Optional[int], approval_id: Any) -> Optional[str]:
    res = load_resource(db, None, company_id, "approval", str(approval_id)) if company_id is not None else None
    return res[1].get("action_type") if res else None
