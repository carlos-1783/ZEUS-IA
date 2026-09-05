"""Add fiscal fields to document_approval

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # document_approvals nunca tuvo una migración que la creara — dependía
    # por completo de Base.metadata.create_all() (app/db/base.py), igual
    # que el resto de tablas documentadas en el Bloque 2 (ver
    # alembic/versions/0043_agent_activities_company_id.py y
    # AUDIT_FIX_BLOQUE2.md). Detectado ejecutando `alembic upgrade head`
    # desde cero contra un PostgreSQL real: rompía aquí con
    # "relation document_approvals does not exist" — la propia migración
    # 0015 ya admitía el síntoma en su docstring sin arreglar la causa
    # (solo hacía no-op si la tabla no existía). Se crea aquí, con el
    # esquema base tal como existía en este punto de la historia (antes de
    # que 0015/0016/0025 añadieran sus columnas propias).
    bind = op.get_bind()
    if 'document_approvals' not in sa.inspect(bind).get_table_names():
        op.create_table(
            'document_approvals',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('agent_name', sa.String(length=50), nullable=False),
            sa.Column('document_type', sa.String(length=100), nullable=False),
            sa.Column('document_payload_json', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
            sa.Column('advisor_email', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_document_approvals_id'), 'document_approvals', ['id'], unique=False)
        op.create_index(op.f('ix_document_approvals_user_id'), 'document_approvals', ['user_id'], unique=False)
        op.create_index(op.f('ix_document_approvals_agent_name'), 'document_approvals', ['agent_name'], unique=False)
        op.create_index(op.f('ix_document_approvals_status'), 'document_approvals', ['status'], unique=False)

    # Agregar campos fiscales a document_approvals
    op.add_column('document_approvals', sa.Column('ticket_id', sa.String(length=100), nullable=True))
    op.add_column('document_approvals', sa.Column('fiscal_document_type', sa.String(length=50), nullable=True))
    op.add_column('document_approvals', sa.Column('export_format', sa.String(length=20), nullable=True))
    op.add_column('document_approvals', sa.Column('exported_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('document_approvals', sa.Column('filed_external_at', sa.DateTime(timezone=True), nullable=True))
    
    # Crear índices
    op.create_index(op.f('ix_document_approvals_ticket_id'), 'document_approvals', ['ticket_id'], unique=False)


def downgrade() -> None:
    # Guardas de existencia (mismo criterio que
    # 0015_document_approvals_missing_columns.py::downgrade, que revierte
    # estas mismas columnas/índice y corre DESPUÉS de esta migración en el
    # sentido de upgrade -> ANTES en el sentido de downgrade): sin esto, un
    # `alembic downgrade base` completo falla aquí con "index does not
    # exist" porque 0015 ya los eliminó al bajar. Encontrado ejecutando el
    # ciclo downgrade/upgrade completo contra un Postgres real por primera
    # vez.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('document_approvals'):
        return
    existing_indexes = {ix['name'] for ix in inspector.get_indexes('document_approvals')}
    existing_columns = {c['name'] for c in inspector.get_columns('document_approvals')}

    if 'ix_document_approvals_ticket_id' in existing_indexes:
        op.drop_index(op.f('ix_document_approvals_ticket_id'), table_name='document_approvals')
    for column in (
        'filed_external_at',
        'exported_at',
        'export_format',
        'fiscal_document_type',
        'ticket_id',
    ):
        if column in existing_columns:
            op.drop_column('document_approvals', column)

    # Simétrico con la rama "Postgres limpio" de upgrade() (que crea la
    # tabla completa si no existía): si esta migración fue la que la creó,
    # el downgrade debe eliminarla — si no, un `alembic downgrade base`
    # completo se rompe después en 0001 ("cannot drop table users because
    # other objects depend on it", la FK de document_approvals.user_id).
    # Guarda de seguridad: solo se elimina si está vacía (nunca se borra una
    # tabla con datos reales de una instalación existente vía create_all()).
    # Encontrado ejecutando el ciclo downgrade/upgrade completo contra un
    # Postgres real por primera vez.
    row_count = bind.execute(sa.text('SELECT count(*) FROM document_approvals')).scalar()
    if row_count == 0:
        op.drop_table('document_approvals')
