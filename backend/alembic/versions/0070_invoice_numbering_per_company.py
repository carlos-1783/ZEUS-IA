"""Numeracion de facturas correlativa POR EMPRESA y serie (contador en BD, sin contar filas)

Antes (0001 + services/invoice_numbering_v1 del commit 61c988a):
- `invoices.invoice_number` tenia un UNIQUE GLOBAL (`ix_invoices_invoice_number`): dos empresas no podian
  tener el mismo numero, asi que la serie INV-YYYYMMDD-N era una unica serie compartida por todos los clientes.
- El helper calculaba N leyendo el maximo de TODAS las empresas: vaciaba `app.current_company_id` para
  saltarse la RLS de `invoices`. Eso dependia de que la policy de 0047 fuera fail-open y es justo lo que el
  endurecimiento de RLS (fail-closed) va a prohibir.

Ahora:
1. Tabla `invoice_counters(company_id, series, last_number)`: un contador por empresa y serie.
2. Funcion `invoice_next_number(company_id, series)` (PostgreSQL): `UPDATE ... SET last_number =
   last_number + 1 ... RETURNING` dentro de la MISMA transaccion que inserta la factura. El UPDATE deja la
   fila del contador bloqueada hasta el commit/rollback: dos altas simultaneas de la misma empresa se
   serializan (la segunda espera y recibe N+1). Si la creacion hace rollback, el UPDATE del contador tambien
   se deshace: el numero NO se consume y no queda hueco (por eso NO es una SEQUENCE: nextval no se deshace
   con rollback). Empresas distintas no se bloquean entre si. SECURITY INVOKER: corre con la RLS del
   llamador; con contexto de empresa A no puede mover el contador de B (policy de `invoice_counters`).
3. Unicidad por empresa: UNIQUE(company_id, invoice_number) en lugar del UNIQUE global. Las filas legacy sin
   empresa (company_id NULL; hoy 0 en la copia de produccion) siguen con numero unico entre ellas mediante un
   indice unico parcial, porque en un UNIQUE compuesto los NULL no chocan entre si.
4. Inicializacion SIN renumerar nada: para cada empresa con facturas INV-YYYYMMDD-N, last_number = mayor N
   existente de esa empresa. La siguiente factura de la empresa sera ese N + 1. Los huecos historicos (la
   serie era global) se quedan como estan: no se toca ninguna factura emitida.
5. Serie TPV `FRA-<ticket>`: no usa contador (deriva del ticket, ya unico por venta via
   `uq_invoices_tpv_sale_id` y `ix_tpv_sales_ticket_id`); el nuevo UNIQUE(company_id, invoice_number) la
   cubre igual.

IDEMPOTENTE (upgrade y downgrade). El arranque de produccion hace `alembic upgrade head || echo WARN` y
despues `create_all` (railway.toml, Dockerfile, app/main.py): si la migracion fallara o no corriera, create_all
crearia `invoice_counters` desde el modelo (sin funcion ni indices) y un upgrade posterior no puede atascarse
con "relation invoice_counters already exists". Por eso cada objeto se crea solo si falta (tabla, indices,
policy), la funcion es CREATE OR REPLACE, y la siembra nunca baja un contador existente
(ON CONFLICT ... GREATEST). Ver tambien scripts/alembic_conditional_stamp.py (ruta legacy).

RLS de `invoice_counters`: ENABLE + FORCE con el MISMO criterio que el resto de tablas de 0047 hoy
(sin contexto -> sin filtro; con contexto -> solo la propia empresa). Cuando se endurezcan todas las policies
a fail-closed, esta se endurece en el mismo paso; el contador NUNCA necesita leer otras empresas.

Downgrade: vuelve al UNIQUE global. Si para entonces dos empresas comparten un numero (ya posible tras el
upgrade), recrear el UNIQUE global es imposible sin renumerar facturas emitidas: el downgrade se ABORTA con
un error explicito que lista cuantos numeros chocan, sin tocar datos.

Revision ID: 0070
Revises: 0069
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None

SERIES_INV = "INV"
# INV-YYYYMMDD-N con N sin ceros a la izquierda y como mucho 9 cifras (cabe en integer).
_INV_REGEX = r"^INV-[0-9]{8}-[1-9][0-9]{0,8}$"

_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION invoice_next_number(p_company_id integer, p_series varchar)
RETURNS integer
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_next integer;
BEGIN
    IF p_company_id IS NULL THEN
        RAISE EXCEPTION 'invoice_next_number: company_id es obligatorio'
            USING ERRCODE = 'not_null_violation';
    END IF;
    IF p_series IS NULL OR p_series !~ '^[A-Z0-9]{1,20}$' THEN
        RAISE EXCEPTION 'invoice_next_number: serie invalida %', p_series
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    UPDATE invoice_counters
       SET last_number = last_number + 1, updated_at = now()
     WHERE company_id = p_company_id AND series = p_series
    RETURNING last_number INTO v_next;

    IF NOT FOUND THEN
        -- Primera factura de la serie para la empresa. ON CONFLICT cubre la carrera de dos primeras
        -- altas simultaneas: la segunda espera al commit de la primera y suma 1 sobre su valor.
        INSERT INTO invoice_counters AS c (company_id, series, last_number)
        VALUES (p_company_id, p_series, 1)
        ON CONFLICT (company_id, series)
        DO UPDATE SET last_number = c.last_number + 1, updated_at = now()
        RETURNING c.last_number INTO v_next;
    END IF;

    RETURN v_next;
END;
$$
"""


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _indexes(bind, table: str) -> dict:
    """{nombre: unique} de los indices de `table` (incluye los UNIQUE de create_all/Index)."""
    return {ix["name"]: bool(ix.get("unique")) for ix in inspect(bind).get_indexes(table)}


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _create_counters_table_if_missing(bind) -> None:
    if _has_table(bind, "invoice_counters"):
        # Creada antes (p. ej. por create_all desde el modelo InvoiceCounter): misma definicion.
        # Lo unico imprescindible para la funcion es la clave (company_id, series) para ON CONFLICT.
        pk = inspect(bind).get_pk_constraint("invoice_counters")
        if sorted(pk.get("constrained_columns") or []) != ["company_id", "series"]:
            raise RuntimeError(
                "upgrade 0070: invoice_counters ya existe pero sin PRIMARY KEY (company_id, series); "
                "revisar a mano antes de continuar. No se ha tocado nada."
            )
        return
    op.create_table(
        "invoice_counters",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("series", sa.String(20), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("company_id", "series", name="pk_invoice_counters"),
        sa.CheckConstraint("last_number >= 0", name="ck_invoice_counters_last_number_non_negative"),
    )


def _seed_counters(bind, pg: bool) -> None:
    """Contador = mayor N existente de cada empresa. Si ya hay fila, nunca se baja (GREATEST): no se
    renumera nada ni se reutiliza un numero ya emitido."""
    if pg:
        op.execute(
            f"""
            INSERT INTO invoice_counters (company_id, series, last_number)
            SELECT company_id, '{SERIES_INV}', max(substring(invoice_number from 14)::integer)
            FROM invoices
            WHERE company_id IS NOT NULL AND invoice_number ~ '{_INV_REGEX}'
            GROUP BY company_id
            ON CONFLICT (company_id, series)
            DO UPDATE SET last_number = GREATEST(invoice_counters.last_number, EXCLUDED.last_number)
            """
        )
        return
    import re

    rx = re.compile(_INV_REGEX)
    best = {}
    for cid, number in bind.execute(
        sa.text("SELECT company_id, invoice_number FROM invoices "
                "WHERE company_id IS NOT NULL AND invoice_number LIKE 'INV-%'")
    ).fetchall():
        if number and rx.match(number):
            best[cid] = max(best.get(cid, 0), int(number[13:]))
    for cid, n in best.items():
        current = bind.execute(
            sa.text("SELECT last_number FROM invoice_counters WHERE company_id = :c AND series = :s"),
            {"c": cid, "s": SERIES_INV},
        ).scalar()
        if current is None:
            bind.execute(
                sa.text("INSERT INTO invoice_counters (company_id, series, last_number) VALUES (:c, :s, :n)"),
                {"c": cid, "s": SERIES_INV, "n": n},
            )
        elif current < n:
            bind.execute(
                sa.text("UPDATE invoice_counters SET last_number = :n WHERE company_id = :c AND series = :s"),
                {"c": cid, "s": SERIES_INV, "n": n},
            )


def upgrade() -> None:
    bind = op.get_bind()
    pg = _is_postgres(bind)

    _create_counters_table_if_missing(bind)
    _seed_counters(bind, pg)

    # Unicidad: global -> por empresa (cada indice solo si falta / si sigue siendo el UNIQUE global).
    ix = _indexes(bind, "invoices")
    if ix.get("ix_invoices_invoice_number") is True:
        op.drop_index("ix_invoices_invoice_number", table_name="invoices")
        ix.pop("ix_invoices_invoice_number")
    if "ix_invoices_invoice_number" not in ix:
        op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"], unique=False)
    if "uq_invoices_company_id_invoice_number" not in ix:
        op.create_index(
            "uq_invoices_company_id_invoice_number", "invoices", ["company_id", "invoice_number"], unique=True
        )
    if "uq_invoices_invoice_number_without_company" not in ix:
        op.create_index(
            "uq_invoices_invoice_number_without_company",
            "invoices",
            ["invoice_number"],
            unique=True,
            postgresql_where=sa.text("company_id IS NULL"),
            sqlite_where=sa.text("company_id IS NULL"),
        )

    if not pg:
        return

    op.execute(_FUNCTION_SQL)

    op.execute("ALTER TABLE invoice_counters ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_counters FORCE ROW LEVEL SECURITY")
    has_policy = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = current_schema() "
                "AND tablename = 'invoice_counters' AND policyname = 'tenant_isolation_invoice_counters')")
    ).scalar()
    if not has_policy:
        op.execute(
            """
            CREATE POLICY tenant_isolation_invoice_counters ON invoice_counters
            USING (
                NULLIF(current_setting('app.current_company_id', true), '') IS NULL
                OR company_id::text = current_setting('app.current_company_id', true)
            )
            """
        )
    # Rol de runtime sin privilegios (si existe en esta BD; ver 0049): necesita leer/escribir el contador.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zeus_app') THEN
                GRANT SELECT, INSERT, UPDATE ON invoice_counters TO zeus_app;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    pg = _is_postgres(bind)

    clashes = bind.execute(
        sa.text("SELECT count(*) FROM (SELECT invoice_number FROM invoices "
                "GROUP BY invoice_number HAVING count(*) > 1) d")
    ).scalar()
    if clashes:
        raise RuntimeError(
            f"downgrade 0070 abortado: {clashes} numero(s) de factura se repiten entre empresas; el UNIQUE global "
            "de invoices.invoice_number no se puede recrear sin renumerar facturas ya emitidas. No se ha tocado nada."
        )

    if pg:
        op.execute("DROP FUNCTION IF EXISTS invoice_next_number(integer, varchar)")
        if _has_table(bind, "invoice_counters"):
            op.execute("DROP POLICY IF EXISTS tenant_isolation_invoice_counters ON invoice_counters")

    ix = _indexes(bind, "invoices")
    if "uq_invoices_invoice_number_without_company" in ix:
        op.drop_index("uq_invoices_invoice_number_without_company", table_name="invoices")
    if "uq_invoices_company_id_invoice_number" in ix:
        op.drop_index("uq_invoices_company_id_invoice_number", table_name="invoices")
    if ix.get("ix_invoices_invoice_number") is not True:
        if "ix_invoices_invoice_number" in ix:
            op.drop_index("ix_invoices_invoice_number", table_name="invoices")
        op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"], unique=True)

    if _has_table(bind, "invoice_counters"):
        op.drop_table("invoice_counters")
