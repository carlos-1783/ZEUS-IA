"""fiscal_profiles/reservations/time_tracking_records: add company_id for tenant scoping

Revision ID: 0058
Revises: 0056
Create Date: 2026-10-04

Nota de numeración: el head de "main" en el momento de crear esta migración
era "0056". La revisión "0057" ya está reservada en la rama
feature/transacciones-zeus-por-tenant (mismo loop de producción, otra tarea
en paralelo) para evitar bloquear ese trabajo. Para no colisionar Revision
IDs al fusionar ambas ramas en main (mismo problema que forzó la renumeración
0043->0048 documentada en 0048_products_company_id_tenant_isolation.py), esta
cadena usa "0058", encadenada directamente tras "0056". Si al fusionar
feature/transacciones-zeus-por-tenant resulta que 0057 reclama un down_revision
distinto, Carlos deberá re-encadenar manualmente (down_revision de 0057 o de
esta 0058) antes de aplicar en producción -- no asumir que el orden final es
este sin revisar el merge.

Contexto (hallazgo E1, auditoría final del núcleo, severidad Media):
varios endpoints de TPV y Control Horario filtraban por
`<Modelo>.user_id == current_user.id` en vez de por la(s) empresa(s) del
usuario (UserCompany). Esto no es una fuga entre empresas distintas (cada
owner seguía aislado de otras empresas), pero es incorrecto para cualquier
empresa con MAS DE UN USUARIO: un segundo encargado vinculado vía
UserCompany no veía el perfil fiscal, las reservas ni los fichajes de SU
PROPIA empresa, solo lo que el mismo habia creado/registrado.

Se añade `company_id` (FK a companies, nullable, ON DELETE SET NULL, con
índice) a fiscal_profiles, reservations y time_tracking_records, siguiendo
el mismo patrón ya usado en tpv_products/tpv_sales (ver 0012 y 0048). Sin
backfill: las filas existentes quedan con company_id NULL y las queries
aplican fallback a `company_id IS NULL AND user_id == current_user.id`
para no perder visibilidad de datos legado de un único usuario (mismo
patrón que _customer_scope_filter en crm_office_service.py y el fix N4 de
quarterly-vat en tpv.py).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0058"
down_revision = "0056"
branch_labels = None
depends_on = None


_TABLES = ("fiscal_profiles", "reservations", "time_tracking_records")


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        cols = {c["name"] for c in inspect(bind).get_columns(table)}
        if "company_id" in cols:
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{table}_company_id",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="SET NULL",
            )
        op.create_index(op.f(f"ix_{table}_company_id"), table, ["company_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        cols = {c["name"] for c in inspect(bind).get_columns(table)}
        if "company_id" not in cols:
            continue
        op.drop_index(op.f(f"ix_{table}_company_id"), table_name=table)
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_company_id", type_="foreignkey")
            batch_op.drop_column("company_id")
