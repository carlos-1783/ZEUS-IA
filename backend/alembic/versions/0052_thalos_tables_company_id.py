"""thalos_events/thalos_alerts/thalos_login_attempts: añadir company_id

Fix estructural de raíz (AUDIT_THALOS_ESTRUCTURAL.md, paso 1) tras 6 vueltas
de mitigaciones interinas (gates de superusuario) en
feature/fix-thalos-shield-real, documentadas en AUDIT_FIX_THALOS_SHIELD.md.
Esas 6 vueltas encontraron, una y otra vez, la misma causa raíz: 3 de las 4
tablas del subsistema de logs de seguridad de THALOS
(thalos_events, thalos_alerts, thalos_login_attempts) no tenían ninguna
columna de tenant, así que cualquier filtrado por empresa era imposible sin
esta migración. `thalos_security_events` ya tenía `company_id` desde la
migración 0030 (thalos_safe_audit_v1) — no se toca aquí.

Mismo patrón ya probado en este repo para el mismo problema en
`agent_activities` (ver `0043_agent_activities_company_id.py` en
`feature/multi-tenant-bd`, commit `6173852`): columna nullable + índice +
FK solo en dialectos que la soportan de verdad (no en SQLite) + backfill
best-effort usando la señal más fiable disponible en cada tabla.

## Backfill — señal usada por tabla (best-effort, documentado con honestidad)

- `thalos_login_attempts`: `email` -> `users.email` -> `user_companies.company_id`
  (primera empresa del usuario). Funciona solo para intentos de login cuyo
  email corresponde a un usuario real registrado. Los intentos de fuerza
  bruta con emails inventados (`brute_xxx@evil.test`, el caso de uso que
  motivó el diseño de esta tabla) quedan `company_id IS NULL` de forma
  honesta e irreversible -- no existe ninguna vía de atribuirlos a una
  empresa real (conclusión ya documentada en AUDIT_FIX_THALOS_SHIELD.md,
  sección 7.3, confirmada de nuevo aquí).
- `thalos_alerts`: (1) `metadata_json['email']` cuando `rule_id =
  'brute_force_email'` (estructura conocida y fiable, ver
  `services/thalos_threat_engine.py::evaluate_events`, que serializa el
  email real como campo JSON estructurado, no solo texto libre); (2) email
  extraído por regex de `message`/`metadata_json` para el resto de reglas
  (best-effort); (3) heredar `company_id` de `thalos_events` vía `event_id`,
  una vez esa tabla ya está backfileada en el paso anterior de esta misma
  migración.
- `thalos_events`: email extraído por regex de `message`/`metadata_json`
  (best-effort). La mayoría de eventos (parseo de líneas de log genéricas)
  no contienen ningún email y quedan `company_id IS NULL` honestamente.

Ningún backfill se inventa una empresa cuando no hay señal real -- las filas
sin atribución fiable quedan `NULL`, que es exactamente lo que la policy de
RLS de `0047_thalos_row_level_security.py` trata como "no visible para
ninguna sesión de tenant concreta" (solo visibles para superusuario/rol de
servicio, o cuando no hay contexto de tenant fijado en la transacción).

Revision ID: 0052
Revises: 0051

Nota de consolidación (feature/consolidacion-final): renumerada de "0046" a
"0052" al fusionar — colisionaba con "0046_missing_tables_create_all_only.py"
(ya mergeado en la rama consolidada, cadena hasta "0051"). Encadenada tras
"0051", sin cambios de lógica.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")


def _add_company_id_column(bind, inspector, table: str) -> None:
    cols = {c["name"] for c in inspector.get_columns(table)}
    if "company_id" in cols:
        return
    op.add_column(table, sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_index(f"ix_{table}_company_id", table, ["company_id"], unique=False)
    # SQLite no soporta ADD CONSTRAINT fuera de modo batch; Postgres
    # (producción/staging) sí. Mismo criterio que 0043_agent_activities_company_id.py.
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            f"fk_{table}_company_id",
            table,
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )


def _resolve_company_for_email(connection, email: Optional[str]) -> Optional[int]:
    if not email:
        return None
    row = connection.execute(
        sa.text(
            """
            SELECT uc.company_id FROM user_companies uc
            JOIN users u ON u.id = uc.user_id
            WHERE lower(u.email) = lower(:email)
            ORDER BY uc.id ASC LIMIT 1
            """
        ),
        {"email": email},
    ).fetchone()
    return row[0] if row else None


def _extract_email(message: Optional[str], metadata_json: Optional[str]) -> Optional[str]:
    if metadata_json:
        try:
            meta = json.loads(metadata_json)
        except (TypeError, ValueError):
            meta = None
        if isinstance(meta, dict) and meta.get("email"):
            return str(meta["email"]).strip()
    if message:
        m = EMAIL_RE.search(message)
        if m:
            return m.group(0)
    return None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    for table in ("thalos_events", "thalos_alerts", "thalos_login_attempts"):
        if table in tables:
            _add_company_id_column(bind, inspector, table)

    connection = bind

    # 1) thalos_login_attempts -- backfill directo email -> user_companies.
    if "thalos_login_attempts" in tables:
        connection.execute(
            sa.text(
                """
                UPDATE thalos_login_attempts
                SET company_id = (
                    SELECT uc.company_id FROM user_companies uc
                    JOIN users u ON u.id = uc.user_id
                    WHERE lower(u.email) = lower(thalos_login_attempts.email)
                    ORDER BY uc.id ASC LIMIT 1
                )
                WHERE company_id IS NULL
                """
            )
        )

    # 2) thalos_events -- backfill best-effort por email embebido en message/metadata_json.
    if "thalos_events" in tables:
        rows = connection.execute(
            sa.text("SELECT id, message, metadata_json FROM thalos_events WHERE company_id IS NULL")
        ).fetchall()
        for row_id, message, metadata_json in rows:
            email = _extract_email(message, metadata_json)
            company_id = _resolve_company_for_email(connection, email)
            if company_id:
                connection.execute(
                    sa.text("UPDATE thalos_events SET company_id = :cid WHERE id = :id"),
                    {"cid": company_id, "id": row_id},
                )

    # 3) thalos_alerts -- metadata_json['email'] (rule brute_force_email) o
    #    regex sobre message/metadata_json; si sigue sin resolver, heredar
    #    de thalos_events.company_id vía event_id (ya backfileado arriba).
    if "thalos_alerts" in tables:
        rows = connection.execute(
            sa.text(
                "SELECT id, event_id, message, metadata_json FROM thalos_alerts WHERE company_id IS NULL"
            )
        ).fetchall()
        for row_id, event_id, message, metadata_json in rows:
            email = _extract_email(message, metadata_json)
            company_id = _resolve_company_for_email(connection, email) if email else None
            if not company_id and event_id:
                ev_row = connection.execute(
                    sa.text("SELECT company_id FROM thalos_events WHERE id = :id"),
                    {"id": event_id},
                ).fetchone()
                if ev_row and ev_row[0]:
                    company_id = ev_row[0]
            if company_id:
                connection.execute(
                    sa.text("UPDATE thalos_alerts SET company_id = :cid WHERE id = :id"),
                    {"cid": company_id, "id": row_id},
                )


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    for table in ("thalos_login_attempts", "thalos_alerts", "thalos_events"):
        if table not in tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "company_id" in cols:
            if bind.dialect.name != "sqlite":
                op.drop_constraint(f"fk_{table}_company_id", table, type_="foreignkey")
            op.drop_index(f"ix_{table}_company_id", table_name=table)
            op.drop_column(table, "company_id")
