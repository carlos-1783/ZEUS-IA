"""
Marketing Integrations v1 — validación, persistencia en company.metadata, actividad.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.db.metadata_utils import set_company_metadata
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

METRICS_COLLECTED = ["ad_spend", "leads_generated", "cost_per_lead", "engagement"]

DEFAULT_SOCIAL = {
    "instagram": {"username": "", "connected": False},
    "facebook": {"page_id": "", "connected": False},
    "whatsapp_business": {"phone_number": "", "connected": False},
    "google_business": {"location_id": "", "connected": False},
    "email_marketing": {"email": "", "connected": False},
}

DEFAULT_ADS = {
    "meta_ads": {"account_id": "", "connected": False, "track_metrics": True},
    "google_ads": {"account_id": "", "connected": False, "track_metrics": True},
}

DEFAULT_PERMISSIONS = {
    "allow_auto_post": False,
    "allow_auto_ads_analysis": True,
    "allow_auto_messages": False,
}

SOCIAL_FIELD_MAP = {
    "instagram": "username",
    "facebook": "page_id",
    "whatsapp_business": "phone_number",
    "google_business": "location_id",
    "email_marketing": "email",
}


def _resolve_company(db: Session, user: User) -> Tuple[Company, int]:
    cid = crm_svc.primary_company_id(db, user)
    if cid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere empresa asociada (company_id obligatorio).",
        )
    company = db.query(Company).filter(Company.id == cid).first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return company, cid


def _env_connected(platform: str) -> bool:
    checks = {
        "instagram": lambda: bool(os.getenv("INSTAGRAM_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")),
        "facebook": lambda: bool(os.getenv("FACEBOOK_PAGE_ID") or os.getenv("FACEBOOK_ACCESS_TOKEN")),
        "whatsapp_business": lambda: bool(os.getenv("TWILIO_ACCOUNT_SID") or os.getenv("WHATSAPP_BUSINESS_TOKEN")),
        "google_business": lambda: bool(os.getenv("GOOGLE_BUSINESS_LOCATION_ID")),
        "email_marketing": lambda: bool(os.getenv("SENDGRID_API_KEY") or os.getenv("SMTP_HOST")),
        "meta_ads": lambda: bool(os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID")),
        "google_ads": lambda: bool(
            os.getenv("GOOGLE_ADS_CUSTOMER_ID") and os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        ),
    }
    fn = checks.get(platform)
    return bool(fn()) if fn else False


def _merge_platform_defaults(stored: Optional[Dict[str, Any]], defaults: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(defaults)
    if not isinstance(stored, dict):
        return out
    for key, base in out.items():
        row = stored.get(key) if isinstance(stored.get(key), dict) else {}
        merged = {**base, **row}
        if merged.get("connected") and _env_connected(key):
            merged["env_ready"] = True
        out[key] = merged
    return out


def get_integrations(db: Session, user: User) -> Dict[str, Any]:
    company, cid = _resolve_company(db, user)
    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    block = meta.get("marketing_integrations_v1") if isinstance(meta.get("marketing_integrations_v1"), dict) else {}

    social = _merge_platform_defaults(block.get("social_platforms"), DEFAULT_SOCIAL)
    ads = _merge_platform_defaults(block.get("ads_platforms"), DEFAULT_ADS)
    permissions = {**DEFAULT_PERMISSIONS, **(block.get("permissions") or {})}

    return {
        "company_id": cid,
        "social_platforms": social,
        "ads_platforms": ads,
        "permissions": permissions,
        "metrics_collected": list(METRICS_COLLECTED),
        "updated_at": block.get("updated_at"),
    }


def _platform_value(social: Dict[str, Any], platform: str) -> str:
    row = social.get(platform) if isinstance(social.get(platform), dict) else {}
    field = SOCIAL_FIELD_MAP.get(platform, "username")
    return str(row.get(field) or "").strip()


def validate_inputs(payload: Dict[str, Any]) -> None:
    """Validar integraciones antes de guardar."""
    social = payload.get("social_platforms") or {}
    ads = payload.get("ads_platforms") or {}

    for platform, field in SOCIAL_FIELD_MAP.items():
        row = social.get(platform) if isinstance(social.get(platform), dict) else {}
        if not row.get("connected"):
            continue
        val = str(row.get(field) or "").strip()
        if not val:
            raise HTTPException(
                status_code=422,
                detail=f"Plataforma social '{platform}' marcada como conectada pero falta el campo obligatorio.",
            )
        if platform == "email_marketing" and "@" not in val:
            raise HTTPException(status_code=422, detail="Email de marketing no válido.")

    for platform in ("meta_ads", "google_ads"):
        row = ads.get(platform) if isinstance(ads.get(platform), dict) else {}
        if row.get("connected") and not str(row.get("account_id") or "").strip():
            raise HTTPException(
                status_code=422,
                detail=f"'{platform}' requiere account_id si está conectada.",
            )


def store_integrations(db: Session, user: User, payload: Dict[str, Any]) -> Dict[str, Any]:
    company, cid = _resolve_company(db, user)
    validate_inputs(payload)

    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    now = datetime.now(timezone.utc).isoformat()

    social_in = payload.get("social_platforms") or {}
    ads_in = payload.get("ads_platforms") or {}
    permissions_in = payload.get("permissions") or {}

    social_out = deepcopy(DEFAULT_SOCIAL)
    for key in social_out:
        row = social_in.get(key) if isinstance(social_in.get(key), dict) else {}
        field = SOCIAL_FIELD_MAP[key]
        social_out[key] = {
            field: str(row.get(field) or "").strip(),
            "connected": bool(row.get("connected")),
        }

    ads_out = deepcopy(DEFAULT_ADS)
    for key in ads_out:
        row = ads_in.get(key) if isinstance(ads_in.get(key), dict) else {}
        ads_out[key] = {
            "account_id": str(row.get("account_id") or "").strip(),
            "connected": bool(row.get("connected")),
            "track_metrics": bool(row.get("track_metrics", True)),
        }

    permissions_out = {**DEFAULT_PERMISSIONS, **permissions_in}

    meta["marketing_integrations_v1"] = {
        "company_id": cid,
        "social_platforms": social_out,
        "ads_platforms": ads_out,
        "permissions": permissions_out,
        "metrics_collected": METRICS_COLLECTED,
        "updated_at": now,
    }
    set_company_metadata(company, meta)
    db.add(company)
    db.commit()
    db.refresh(company)

    log_marketing_connected(db, user, company_id=cid, integrations=meta["marketing_integrations_v1"])

    return get_integrations(db, user)


def log_marketing_connected(
    db: Session,
    user: User,
    *,
    company_id: int,
    integrations: Dict[str, Any],
) -> None:
    """Actividad legible: marketing_connected."""
    _ = db
    connected_names: List[str] = []
    for name, row in (integrations.get("social_platforms") or {}).items():
        if isinstance(row, dict) and row.get("connected"):
            connected_names.append(name.replace("_", " ").title())
    for name, row in (integrations.get("ads_platforms") or {}).items():
        if isinstance(row, dict) and row.get("connected"):
            connected_names.append(name.replace("_", " ").title())

    summary = (
        f"Integraciones de marketing guardadas: {', '.join(connected_names)}"
        if connected_names
        else "Integraciones de marketing actualizadas (sin canales conectados aún)."
    )
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="PERSEO",
            action_type="marketing_connected",
            action_description=summary,
            details={"company_id": company_id, "platforms": connected_names},
            user_email=getattr(user, "email", None),
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception:
        logger.exception("log_marketing_connected failed company_id=%s", company_id)


def collect_metrics_snapshot(db: Session, user: User) -> Dict[str, Any]:
    """Métricas agregadas si hay ads conectados y análisis automático permitido."""
    data = get_integrations(db, user)
    perms = data.get("permissions") or {}
    if not perms.get("allow_auto_ads_analysis"):
        return {"enabled": False, "reason": "Análisis automático desactivado"}

    ads = data.get("ads_platforms") or {}
    any_ads = any(
        isinstance(row, dict) and row.get("connected") and row.get("track_metrics")
        for row in ads.values()
    )
    if not any_ads:
        return {"enabled": False, "reason": "Sin plataformas de ads conectadas"}

    # Placeholder estructurado — listo para APIs reales Meta/Google
    return {
        "enabled": True,
        "period": "last_30_days",
        "metrics": {
            "ad_spend": 0.0,
            "leads_generated": 0,
            "cost_per_lead": 0.0,
            "engagement": 0.0,
        },
        "source": "marketing_integrations_v1",
    }
