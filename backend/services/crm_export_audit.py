"""Traza de exportaciones de datos personales del CRM oficina (CSV / Excel).

Exportar clientes, expedientes o cobros saca datos personales de ZEUS: debe quedar
registro verificable de quien, que entidad, en que formato y cuantas filas (RGPD,
responsabilidad proactiva). Se escribe en el log de aplicacion y en crm_activity_log
de cada empresa del usuario.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.crm_office import CrmActivityLog
from app.models.user import User
from services import crm_office_service as crm_svc

logger = logging.getLogger(__name__)


def log_personal_data_export(db: Session, user: User, *, entity: str, fmt: str, rows: int) -> None:
    company_ids = crm_svc.company_ids_for_user(db, user)
    logger.info(
        "crm_export entity=%s format=%s rows=%s user_id=%s company_ids=%s",
        entity, fmt, rows, user.id, company_ids,
    )
    if not company_ids:
        # Cuenta sin empresa: crm_activity_log exige company_id; queda la traza en el log.
        return
    try:
        for cid in company_ids:
            db.add(
                CrmActivityLog(
                    company_id=cid,
                    user_id=user.id,
                    action="data_export",
                    summary=f"Exportacion {entity} ({fmt}): {rows} filas",
                    payload={"entity": entity, "format": fmt, "rows": rows},
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        # La exportacion ya es del propio tenant; si falla la traza en BD no se oculta.
        logger.exception("crm_export: no se pudo registrar la traza en crm_activity_log user_id=%s", user.id)
