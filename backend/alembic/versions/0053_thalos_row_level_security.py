"""Row Level Security (PostgreSQL) para las 4 tablas de logs de THALOS

AUDIT_THALOS_ESTRUCTURAL.md, paso 2. Segunda capa de aislamiento a nivel de
base de datos para `thalos_events`, `thalos_alerts`, `thalos_security_events`
y `thalos_login_attempts` -- las mismas 4 tablas cuyo aislamiento dependió,
durante las 6 vueltas de `feature/fix-thalos-shield-real`
(`AUDIT_FIX_THALOS_SHIELD.md`), únicamente de que cada endpoint recordara
aplicar un gate de superusuario. RLS no sustituye esos gates (se mantienen
como defensa en profundidad) -- añade una capa que no depende de que el
código de la aplicación acierte siempre, ni de que un futuro endpoint nuevo
recuerde el mismo gate.

Reutiliza EXACTAMENTE el mismo patrón ya diseñado y validado contra un
PostgreSQL real de Railway en `feature/multi-tenant-bd`
(`0047_row_level_security.py`, commit `6173852`, corregido en `dec54c0`
tras encontrar que RLS quedaba inerte si la app conecta como superusuario
de Postgres -- ver `app/db/tenant_context.py` y el rol `zeus_app` descrito
ahí). Esa rama NO está fusionada aquí -- este archivo es una adaptación
propia para las 4 tablas de THALOS, mismo diseño, mismas policies con la
misma forma.

Solo se ejecuta en PostgreSQL -- no-op completo en SQLite (RLS no existe
ahí; local/tests siguen exactamente igual).

## Diseño: "fail-open cuando no hay contexto"

Cada policy dice: "si nadie estableció el contexto de tenant para esta
transacción (`app.current_company_id`), deja ver todo (igual que antes de
esta migración); si SÍ se estableció, filtra de verdad, y las filas sin
`company_id` conocido (backfill imposible, ver 0046) quedan invisibles para
cualquier tenant concreto". Esto es deliberado: activar RLS no puede romper
ninguna query existente que no haya sido migrada explícitamente a
`get_db_scoped()` (workers de fondo, scripts, Alembic mismo, endpoints
todavía sin tocar). Da protección real solo donde la aplicación ya lo pide
explícitamente.

## IMPORTANTE -- pendiente de verificación contra Postgres real

Este entorno de desarrollo (worktree `feature/fix-thalos-shield-real`) solo
tuvo acceso a SQLite durante esta sesión -- no había Docker ni un Postgres
de prueba/staging con credenciales conocidas disponibles (se encontró un
servicio PostgreSQL 17 local preexistente del propio Carlos, sin
credenciales conocidas y sin relación documentada con este proyecto; no se
intentó adivinar su contraseña ni usarlo como base de pruebas desechable,
por prudencia). La sintaxis SQL de este archivo replica al carácter el
patrón de `0047_row_level_security.py` (ya verificado con éxito contra
Postgres real de Railway en `dec54c0`), pero **NO se ha ejecutado ni
verificado en vivo contra ningún PostgreSQL real en esta sesión** -- ver
AUDIT_THALOS_ESTRUCTURAL.md para el detalle exacto de qué se verificó
(no-op en SQLite, revisión de código línea a línea) y qué NO
(comportamiento real de `ENABLE`/`FORCE ROW LEVEL SECURITY` y las policies
contra un servidor Postgres real, y muy especialmente el hallazgo crítico
de `dec54c0`: verificar que la app NO conecta como superusuario de
Postgres en el entorno donde se despliegue esto). Tratar como bloqueante
antes de confiar en esta migración para producción: ejecutarla contra
Railway staging con el rol `zeus_app` (o equivalente sin `BYPASSRLS`) y
repetir la prueba de aislamiento cruzado de dos tenants, igual que hizo
`dec54c0` para Bloque 2.

Revision ID: 0053
Revises: 0052

Nota de consolidación (feature/consolidacion-final): renumerada de "0047" a
"0053" al fusionar — colisionaba con "0047_row_level_security.py" (ya
mergeado, la migración de multi-tenant-bd citada en este mismo docstring).
Encadenada tras "0052" (la migración 0046→0052 de arriba), sin cambios de
lógica.
"""
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

_TABLES_WITH_OWN_COMPANY_ID = (
    "thalos_events",
    "thalos_alerts",
    "thalos_security_events",
    "thalos_login_attempts",
)


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _enable_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{table} ON {table}
        USING (
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)
        )
        """
    )


def upgrade() -> None:
    if not _is_postgres():
        return

    for table in _TABLES_WITH_OWN_COMPANY_ID:
        _enable_policy(table)


def downgrade() -> None:
    if not _is_postgres():
        return

    for table in reversed(_TABLES_WITH_OWN_COMPANY_ID):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
