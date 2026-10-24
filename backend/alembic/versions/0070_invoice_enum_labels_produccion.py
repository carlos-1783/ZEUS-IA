"""labels de los ENUM invoicestatus/invoicetype alineadas con produccion

Revision ID: 0070
Revises: 0069
Create Date: 2026-10-24

La 0001 crea los tipos ENUM de PostgreSQL `invoicestatus` e `invoicetype` con labels en
ingles ('draft', 'invoice', ...). En produccion (enum_range confirmado en Railway) los tipos
tienen otras labels, que son las que ahora usa app/models/erp.py como .value:

  invoicetype:   invoice -> factura, estimate -> estimación
                 (credit_note y proforma iguales)
  invoicestatus: draft -> borrador, sent -> enviado, paid -> pagado,
                 void -> anulado, overdue -> vencido (partially_paid igual)

Esta migracion deja una BD nueva (creada con la 0001) con las labels de produccion.
Solo PostgreSQL; en SQLite (sin tipos ENUM nativos) es un no-op.

Idempotente: cada `ALTER TYPE ... RENAME VALUE` solo se ejecuta si la label vieja existe y
la nueva no, asi que en produccion (ya con las labels nuevas) es un no-op. RENAME VALUE
cambia la etiqueta del tipo: las filas existentes conservan su valor (no se borra ni
reescribe ningun dato). Si el tipo no existe, no hace nada.

Rollback: `alembic downgrade 0069` renombra de vuelta (mismas condiciones, simetrico).
OJO: en produccion el downgrade SI renombraria las labels a ingles y desalinearia el
modelo actual; solo tiene sentido junto con volver al codigo anterior.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None

# (tipo, label de la 0001, label de produccion)
_RENAMES = (
    ("invoicetype", "invoice", "factura"),
    ("invoicetype", "estimate", "estimación"),
    ("invoicestatus", "draft", "borrador"),
    ("invoicestatus", "sent", "enviado"),
    ("invoicestatus", "paid", "pagado"),
    ("invoicestatus", "void", "anulado"),
    ("invoicestatus", "overdue", "vencido"),
)

_LABELS_SQL = sa.text(
    "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
    "WHERE t.typname = :typ"
)


def _rename(pairs) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for typ, old, new in pairs:
        labels = {r[0] for r in bind.execute(_LABELS_SQL, {"typ": typ})}
        if old in labels and new not in labels:
            # Identificadores fijos de esta migracion (no entrada de usuario); las labels van
            # como literales SQL con comillas escapadas.
            old_q = old.replace("'", "''")
            new_q = new.replace("'", "''")
            op.execute(f"ALTER TYPE {typ} RENAME VALUE '{old_q}' TO '{new_q}'")


def upgrade() -> None:
    _rename(_RENAMES)


def downgrade() -> None:
    _rename(tuple((typ, new, old) for typ, old, new in _RENAMES))
