"""stored_files: registro de ficheros en almacenamiento externo (Cloudflare R2)

Revision ID: 0063
Revises: 0062
Create Date: 2026-10-12

Fase 2 / Step 1 (hallazgos C1 y A2 de la auditoria): las subidas dejaban el binario en
STATIC_DIR (disco efimero de Railway) y lo publicaban sin autenticacion bajo /static.
Ahora el binario va a R2 bajo `empresa/{company_id}/{categoria}/...` y esta tabla
registra a que empresa pertenece cada objeto.

Solo crea una tabla nueva: no toca ninguna existente ni mueve datos. Los ficheros
antiguos que sigan en /data/static/uploads se migran con
`scripts/migrate_static_uploads_to_r2.py` (dry-run por defecto), que es un paso aparte.

Rollback: `alembic downgrade 0062` elimina la tabla. Si ya se habian subido ficheros,
los objetos de R2 quedan huerfanos (no se borran desde aqui).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

_TABLE = "stored_files"


def upgrade() -> None:
    if _TABLE in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("legacy_path", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("object_key", name="uq_stored_files_object_key"),
        sa.UniqueConstraint("legacy_path", name="uq_stored_files_legacy_path"),
    )
    op.create_index("ix_stored_files_company_id", _TABLE, ["company_id"])
    op.create_index("ix_stored_files_user_id", _TABLE, ["user_id"])
    op.create_index("ix_stored_files_category", _TABLE, ["category"])


def downgrade() -> None:
    if _TABLE not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_stored_files_category", table_name=_TABLE)
    op.drop_index("ix_stored_files_user_id", table_name=_TABLE)
    op.drop_index("ix_stored_files_company_id", table_name=_TABLE)
    op.drop_table(_TABLE)
