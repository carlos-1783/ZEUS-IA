"""consentimiento de envios: columnas de consentimiento/baja y registro outbound_messages

Revision ID: 0069
Revises: 0068
Create Date: 2026-10-13

Fase 2 / envios con consentimiento (hallazgos #3, #4, #15 de la auditoria final):
- customers.marketing_consent (bool, false por defecto), marketing_consent_at,
  marketing_consent_source y marketing_unsubscribed_at: sin consentimiento registrado o con
  baja, el cliente NO recibe campanas ni envios directos.
- reservations.whatsapp_consent (bool, false por defecto) y whatsapp_consent_at: la reserva
  publica solo confirma por WhatsApp si el cliente marco la casilla.
- Tabla outbound_messages: registro de cada envio/bloqueo por empresa (destinatario en hash y
  enmascarado, nunca el cuerpo) y ventana del limite de envios por empresa.

Idempotente: cada columna/tabla solo se crea si no existe. Las filas existentes quedan con
consentimiento = false (nadie recibe comerciales hasta que se registre su consentimiento).
NO esta aplicada en produccion.

Rollback: `alembic downgrade 0068` elimina las columnas nuevas y la tabla outbound_messages.
Se pierden los consentimientos/bajas registrados y el historial de envios: exportar antes
(SELECT id, company_id, marketing_consent, marketing_consent_at, marketing_unsubscribed_at
FROM customers) si hay que conservarlos.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

_CUSTOMER_COLUMNS = (
    ("marketing_consent", lambda: sa.Column("marketing_consent", sa.Boolean(), nullable=True, server_default=sa.false())),
    ("marketing_consent_at", lambda: sa.Column("marketing_consent_at", sa.DateTime(timezone=True), nullable=True)),
    ("marketing_consent_source", lambda: sa.Column("marketing_consent_source", sa.String(length=50), nullable=True)),
    ("marketing_unsubscribed_at", lambda: sa.Column("marketing_unsubscribed_at", sa.DateTime(timezone=True), nullable=True)),
)
_RESERVATION_COLUMNS = (
    ("whatsapp_consent", lambda: sa.Column("whatsapp_consent", sa.Boolean(), nullable=True, server_default=sa.false())),
    ("whatsapp_consent_at", lambda: sa.Column("whatsapp_consent_at", sa.DateTime(timezone=True), nullable=True)),
)

_TABLE = "outbound_messages"
_INDEXES = (
    ("ix_outbound_messages_id", ["id"]),
    ("ix_outbound_messages_company_id", ["company_id"]),
    ("ix_outbound_messages_user_id", ["user_id"]),
    ("ix_outbound_messages_channel", ["channel"]),
    ("ix_outbound_messages_purpose", ["purpose"]),
    ("ix_outbound_messages_recipient_hash", ["recipient_hash"]),
    ("ix_outbound_messages_status", ["status"]),
    ("ix_outbound_messages_created_at", ["created_at"]),
)


def _add_columns(table: str, columns) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    for name, build in columns:
        if name not in existing:
            op.add_column(table, build())


def _drop_columns(table: str, columns) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    for name, _build in reversed(columns):
        if name in existing:
            with op.batch_alter_table(table) as batch:
                batch.drop_column(name)


def upgrade() -> None:
    _add_columns("customers", _CUSTOMER_COLUMNS)
    _add_columns("reservations", _RESERVATION_COLUMNS)

    if _TABLE in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("recipient_kind", sa.String(length=20), nullable=True),
        sa.Column("recipient_ref_id", sa.Integer(), nullable=True),
        sa.Column("recipient_hash", sa.String(length=64), nullable=False),
        sa.Column("recipient_masked", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for name, cols in _INDEXES:
        op.create_index(name, _TABLE, cols)


def downgrade() -> None:
    if _TABLE in inspect(op.get_bind()).get_table_names():
        for name, _cols in reversed(_INDEXES):
            op.drop_index(name, table_name=_TABLE)
        op.drop_table(_TABLE)
    _drop_columns("reservations", _RESERVATION_COLUMNS)
    _drop_columns("customers", _CUSTOMER_COLUMNS)
