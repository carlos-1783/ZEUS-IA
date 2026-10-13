"""zeus_inbox_items: bandeja de entrada de ZEUS (documentos recibidos por foto/PDF)

Revision ID: 0068
Revises: 0067
Create Date: 2026-10-13

Fase 2 / Sistema Jarvis (ZEUS recepcionista): el usuario envia una foto o PDF a
POST /api/v1/zeus/inbox; el binario va a R2 (stored_files, categoria "inbox") y esta tabla
registra la entrada: empresa, fichero, clasificacion del modelo de vision (sin campos
inventados), validacion de coherencia, agente asignado y la revision pendiente creada en
document_approvals.

Solo crea una tabla nueva (idempotente: si ya existe no hace nada). No toca tablas
existentes ni mueve datos. NO esta aplicada en produccion.

Rollback: `alembic downgrade 0067` elimina la tabla. Los objetos de R2 (stored_files) y las
revisiones de document_approvals creadas desde la bandeja NO se borran: quedan como
ficheros/revisiones normales de la empresa.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

_TABLE = "zeus_inbox_items"
_INDEXES = (
    ("ix_zeus_inbox_items_id", ["id"]),
    ("ix_zeus_inbox_items_company_id", ["company_id"]),
    ("ix_zeus_inbox_items_user_id", ["user_id"]),
    ("ix_zeus_inbox_items_stored_file_id", ["stored_file_id"]),
    ("ix_zeus_inbox_items_status", ["status"]),
    ("ix_zeus_inbox_items_doc_type", ["doc_type"]),
    ("ix_zeus_inbox_items_assigned_agent", ["assigned_agent"]),
)


def upgrade() -> None:
    if _TABLE in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "stored_file_id",
            sa.String(length=32),
            sa.ForeignKey("stored_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pendiente_clasificacion"),
        sa.Column("doc_type", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("extracted_json", sa.Text(), nullable=True),
        sa.Column("validation_json", sa.Text(), nullable=True),
        sa.Column("classification_error", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("assigned_agent", sa.String(length=32), nullable=True),
        sa.Column(
            "document_approval_id",
            sa.Integer(),
            sa.ForeignKey("document_approvals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
    )
    for name, cols in _INDEXES:
        op.create_index(name, _TABLE, cols)


def downgrade() -> None:
    if _TABLE not in inspect(op.get_bind()).get_table_names():
        return
    for name, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
