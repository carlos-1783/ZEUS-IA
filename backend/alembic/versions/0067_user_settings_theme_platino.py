"""user_settings.theme: default 'light' (platino es el tema base)

Revision ID: 0067
Revises: 0064
Create Date: 2026-10-12

Fase 2 / JARVIS: el tema base aprobado es el PLATINO ('light'); el oscuro queda como opcion
del cliente. Solo cambia el server_default de la columna: NO toca filas existentes, porque no
se puede distinguir a quien eligio 'dark' a proposito de quien lo tiene por el default antiguo.
Si se decide migrar a todos a platino, es una decision aparte:
    UPDATE user_settings SET theme = 'light' WHERE theme = 'dark';   -- no se ejecuta aqui

Nota de integracion: al juntar ramas de Fase 2, encadenar tras la ultima revision (0065/0066)
para no dejar varias cabezas.

Rollback: `alembic downgrade 0064` restaura server_default 'dark'.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0067"
down_revision = "0064"
branch_labels = None
depends_on = None


def _has_theme() -> bool:
    insp = inspect(op.get_bind())
    if "user_settings" not in insp.get_table_names():
        return False
    return any(c["name"] == "theme" for c in insp.get_columns("user_settings"))


def _set_default(value: str) -> None:
    if not _has_theme():
        return
    with op.batch_alter_table("user_settings") as batch:
        batch.alter_column("theme", existing_type=sa.String(32), existing_nullable=False,
                           server_default=value)


def upgrade() -> None:
    _set_default("light")


def downgrade() -> None:
    _set_default("dark")
