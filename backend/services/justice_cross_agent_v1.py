"""Cross-agent compliance signals → compliance_events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.compliance_event import ComplianceEvent
from app.models.user import User


def _add(db: Session, event_type: str, severity: str, source: str, details: Dict[str, Any]) -> None:
    exists = (
        db.query(ComplianceEvent)
        .filter(
            ComplianceEvent.event_type == event_type,
            ComplianceEvent.source == source,
            ComplianceEvent.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
        )
        .first()
    )
    if exists:
        return
    db.add(
        ComplianceEvent(
            event_type=event_type,
            severity=severity,
            source=source,
            details_json=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


def sync_cross_agent_events(db: Session, user: User) -> Dict[str, Any]:
    """THALOS, AFRODITA, PERSEO, RAFAEL → compliance_events."""
    synced = {"thalos": 0, "afrodita": 0, "perseo": 0, "rafael": 0}

    try:
        from app.models.thalos_alert import ThalosAlert

        # AUDIT_THALOS_ESTRUCTURAL.md, paso 4: tras la migración
        # 0046_thalos_tables_company_id.py, ThalosAlert.company_id ya existe
        # de verdad -- se filtra por la empresa del usuario que dispara el
        # audit (GET /justice/audit) en vez de leer TODAS las alertas
        # abiertas de TODAS las empresas, para no inyectar detalles de otra
        # empresa (alert_id/title/rule_id) en compliance_events con cada
        # llamada de un usuario normal.
        #
        # Esto NO permite retirar el gate de superusuario de
        # GET /justice/compliance-events (app/api/v1/endpoints/justice.py):
        # ComplianceEvent en sí sigue sin tener company_id (es una tabla
        # global, y su propio `_add` deduplica por event_type+source+ventana
        # de 24h a nivel GLOBAL, no por empresa), así que una fila ya escrita
        # por esta función sigue siendo visible a cualquiera que lea la tabla
        # sin ningún filtro. El gate de superusuario en el endpoint de
        # lectura sigue siendo la única protección real de esa lectura; este
        # cambio solo reduce qué se escribe, no relaja quién puede leerlo.
        # Superusuarios conservan visibilidad global (mismo criterio que
        # `get_db_scoped`).
        alerts_query = db.query(ThalosAlert).filter(ThalosAlert.resolved.is_(False))
        if not getattr(user, "is_superuser", False):
            from services.workspace_deliverables import primary_company_id_for_user

            company_id = primary_company_id_for_user(db, user)
            alerts_query = alerts_query.filter(ThalosAlert.company_id == company_id)
        open_alerts = alerts_query.limit(10).all()
        for alert in open_alerts:
            _add(
                db,
                "security_alert",
                alert.level or "high",
                "THALOS",
                {"alert_id": alert.id, "title": alert.title, "rule_id": alert.rule_id},
            )
            synced["thalos"] += 1
    except Exception:
        pass

    try:
        from app.models.company_employee import CompanyEmployee

        emp_count = (
            db.query(CompanyEmployee)
            .filter(CompanyEmployee.user_id == user.id, CompanyEmployee.is_active.is_(True))
            .count()
        )
        if emp_count == 0:
            _add(db, "hr_compliance_gap", "medium", "AFRODITA", {"issue": "no_active_employees"})
            synced["afrodita"] += 1
    except Exception:
        pass

    try:
        from app.models.perseo_job import PerseoJob

        failed_jobs = (
            db.query(PerseoJob)
            .filter(PerseoJob.user_id == user.id, PerseoJob.status == "failed")
            .count()
        )
        if failed_jobs:
            _add(
                db,
                "marketing_content_risk",
                "low",
                "PERSEO",
                {"failed_jobs": int(failed_jobs)},
            )
            synced["perseo"] += 1
    except Exception:
        pass

    try:
        from app.models.expense import Expense

        unlinked = db.query(Expense).filter(Expense.created_by == user.id).count()
        if unlinked > 0:
            _add(
                db,
                "fiscal_data_review",
                "low",
                "RAFAEL",
                {"expense_records": int(unlinked)},
            )
            synced["rafael"] += 1
    except Exception:
        pass

    db.flush()
    return {"synced": synced, "real_execution": True}
