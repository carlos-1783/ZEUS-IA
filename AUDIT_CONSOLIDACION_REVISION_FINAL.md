# Auditoria independiente final - feature/consolidacion-final

**Revisor**: revisor-independiente (agente separado del ejecutor-produccion)
**Rama auditada**: feature/consolidacion-final
**Commit auditado**: d5bbb55 (176 commits desde main@97b949a)
**Fecha**: 2026-08-27
**Metodologia**: cero confianza en lo escrito por los reportes previos
(CONSOLIDACION_FINAL.md, AUDIT_PERSEO_GOOGLE_ADS_REAL.md,
AUDIT_JUSTICIA_ESTADO_FINAL.md). Cada afirmacion se repitio con
herramientas propias: servidores Uvicorn nuevos, bases de datos SQLite
nuevas, tenants nuevos registrados en esta sesion, tokens nuevos, un
pytest propio y un navegador Playwright propio contra un vite arrancado
manualmente en este worktree. Ningun token, tenant o resultado pegado de
sesiones anteriores fue reutilizado.

---

## 1. Los 4 hallazgos criticos - verificacion en vivo

Servidor propio: uvicorn sobre backend/zeus_reviewer_test.db (SQLite
nueva), puerto 8912. Tenants propios: reva.reviewer@gmail.com (company_id
1), revb.reviewer@gmail.com (company_id 2), mas revonb.reviewer@gmail.com
para el ciclo de onboarding.

### 1.1 GET /api/v1/metrics/dashboard

GET /metrics/dashboard  (sin token) -> 401 "No se pudieron validar las credenciales"
GET /metrics/dashboard  (token A)   -> 200 total_interactions:4
GET /metrics/dashboard  (token B)   -> 200 total_interactions:4   (coincidencia esperada:
ambos tenants recien registrados tienen el mismo bootstrap de actividades)

Para descartar que la coincidencia (4 y 4) fuera en realidad un agregado
global filtrado por casualidad, anadi 3 actividades reales solo al
tenant A (POST /activities/log, agent_name=ZEUS,
action_type=reviewer_test_N) y repeti la consulta:

GET /metrics/dashboard (token A) -> total_interactions:7   (4+3, sube)
GET /metrics/dashboard (token B) -> total_interactions:4   (sin cambio)

Confirmado con SQL directo sobre agent_activities: las filas de A
(company_id=1) y B (company_id=2) son conjuntos disjuntos de IDs.
Veredicto: CONFIRMADO - 401 sin token, aislamiento real por tenant.

### 1.2 GET /api/v1/invoices/, /products/, /customers

GET /invoices/  (sin token) -> 401
GET /invoices/ , /products/ , /customers  (token A, vacio) -> 200, data:[], total:0
POST /products/   (token A) -> 201 (sin LookupError de enum)
POST /customers   (token A) -> 201
POST /invoices/   (token A, 1 item qty=2 x 50 euros + IVA 21%) -> 201,
subtotal:100.0, tax_amount:21.0, total:121.0 (no cero -> el fix de flush+expire de items funciona)

GET /invoices/ , /products/ , /customers  (token B) -> 200, data:[], total:0
(NO ve nada de A, pese a que A ya tiene datos reales)
GET /invoices/1  (token B, factura de A) -> 404
GET /invoices/1  (token A, su propia factura) -> 200, datos completos

No se observo el bug de audiencia JWT (audience must be a string or None)
en ningun momento. Veredicto: CONFIRMADO.

### 1.3 GET/POST /api/v1/google/*

Los 10 endpoints (calendar/events, calendar/event, gmail/send,
gmail/inbox, drive/upload, drive/files, sheets/create,
sheets/write, sheets/read, status), probados sin token:
los 10 devuelven 401. Veredicto: CONFIRMADO.

### 1.4 Onboarding - ciclo completo, no solo la mitad

POST /auth/register  (revonb.reviewer@gmail.com, restaurant) -> 201, company_id=3
GET /auth/onboarding/status  (inmediato) ->
questionnaire_completed: false, setup_completed: false,
setup_inferred: false, checks: tpv_products: 4,
has_tpv_profile: true, company_employees_count: 1

Confirma que el falso positivo NO ocurre: pese a las 4 senales
auto-generadas (identicas a las que antes disparaban setup_completed:true
inmediato), el usuario nuevo ve setup_completed:false.

POST /auth/onboarding/questionnaire  (employees_count:5, uses_tpv:true,
business_hours "L-V 9:00-18:00") -> 200
success:true, company_id:3, message: Cuestionario guardado correctamente,
fallback_mode:false, warnings: vacio

GET /auth/onboarding/status  (despues) ->
questionnaire_completed: true, setup_completed: true,
existing_questionnaire con employees_count:5, uses_tpv:true,
business_hours "L-V 9:00-18:00"

Ciclo completo confirmado de principio a fin, sin el 500 de doble sesion
documentado en el hallazgo historico. Veredicto: CONFIRMADO.

---

## 2. Los 6 agentes

### ZEUS, RAFAEL, THALOS, AFRODITA (spot-check rapido, servidor nuevo puerto 8913, tenant agentcheck.reviewer@gmail.com)

- ZEUS: endpoint agents/status (con token) -> payload real con 6 agentes,
decisions_today/uptime/last_activity calculados de agent_activities
(ZEUS CORE decisions_today:2, PERSEO offline, no valores fijos).
- THALOS: force un login fallido real (endpoint auth/login con password
incorrecta) -> 401, y confirme por SQL directo sobre thalos_login_attempts
dos filas reales: una de exito (success=1) del registro/login inicial y
una de fallo (success=0) del intento incorrecto, ambas con el email real
y timestamp real.
- RAFAEL: endpoint expenses (POST) con datos completos (supplier_name,
base_amount:82.64, tax_amount:17.36) -> 201, persistido con company_id:1
real; sin token -> 401; con campos incompletos -> 422 de validacion
Pydantic real (no un stub).
- AFRODITA: endpoints afrodita ops v1 inventory y afrodita rrhh v1 employees
(con token) -> datos reales derivados de productos TPV auto-creados en el
registro y del empleado owner real (employee_code U2-OWNER); ambos
correctamente etiquetados execution_mode SIMULATED y writes_enabled false
porque el modo de escritura real esta detras de flags - esto es honesto
(declara su propio estado), no una simulacion oculta. Sin token -> 401.

Veredicto: los 4 agentes siguen con logica real, confirmado con pruebas propias.

### PERSEO - Google Ads (create_google_campaign)

Reproducido con variables de entorno de PRUEBA (nunca credenciales reales),
directamente sobre backend servicio perseo_ads_engine_v2.py:

GOOGLE_ADS_CUSTOMER_ID=1234567890 GOOGLE_ADS_DEVELOPER_TOKEN=reviewer-fake-token
_google_configured() -> True
create_google_campaign(name=...) -> HTTPException 501
error google_ads_client_not_implemented, message: no esta implementado -
la campana NO se ha creado en Google Ads

Sin env vars:
_google_configured() -> False
create_google_campaign(name=...) -> HTTPException 503 error google_ads_not_configured

En NINGUN momento se observo success true, campaign_id None, simulated
False. Inspeccion del codigo (perseo_ads_engine_v2.py lineas 66-89)
confirma un unico camino de ejecucion sin ramas muertas: o falla 503 (no
configurado) o falla 501 (configurado pero sin cliente real) - no existe
ninguna tercera rama con exito falso. Veredicto: CONFIRMADO. El hallazgo
historico de Google Ads no se reproduce en el codigo actual.

### JUSTICIA - las dos correcciones nuevas

(a) Handler de automatizacion real (no boilerplate fijo): genere un
contrato REAL para un tenant B nuevo (revb.reviewer@gmail.com, endpoint
justice/contracts/generate, resultado db_id:1, document_id fc5e9158),
encole una actividad real (endpoint activities/log, agent_name JUSTICIA,
action_type compliance_check) e invoque handle_justicia_task directamente
contra esa actividad. El handler devolvio el contrato REAL recien creado
por ese usuario (con su document_id real, status draft,
pending_documents total_pending 1) - no el texto fijo de politica de
privacidad ni docs_generated 3. Ademas probe el caso sin usuario
resoluble: devuelve status failed, real_execution false, sin simular exito.

(b) Fuga multi-tenant en compliance_events corregida: genere un llamado a
justice/gdpr con tenant A (creo 2 ComplianceEvent reales) y consulte
justice/status con tenant B (sin actividad propia):

tenant B (normal) -> compliance_events null, compliance_events_note
explicando que esta oculto para no superusuario
tenant A (normal, mismo que genero los eventos) -> tambien null + nota
(ni siquiera el propio generador ve el agregado global si no es superusuario)

Promovi a tenant A a superusuario directamente en BD (solo para la prueba,
con re-login para refrescar el JWT) y repeti:

tenant A (superusuario) -> justice/status -> compliance_events 3
tenant A (superusuario) -> justice/audit -> compliance_events_count 5

Y confirme que el listado justice/compliance-events sigue devolviendo 403
a un usuario normal (tenant B). Veredicto: CONFIRMADO - el conteo agregado
global ya no se expone a usuarios normales, solo a superusuario.

---

## 3. Migraciones Alembic - HALLAZGO QUE IMPIDE EL CIERRE

Estructura (correcta, confirmado):

alembic heads -> 0053 (head), una sola cabeza
53 archivos en alembic versions, 53 revisiones unicas, 0 IDs duplicados

Esto coincide exactamente con lo documentado.

Ejecucion real desde cero (lo que realmente se pidio verificar) - FALLA:

Ejecute alembic upgrade head contra una base de datos SQLite completamente
nueva y vacia (creada por mi en esta sesion, nunca usada antes, ruta fuera
del repositorio en el directorio temporal de pruebas). El resultado:

INFO Running upgrade 0011 -> 0012, ZEUS_MULTITENANT_MIGRATION_SAFE_001...
NotImplementedError: No support for ALTER of constraints in SQLite dialect.
Please refer to the batch mode feature which allows for SQLite migrations
using a copy-and-move strategy.

La migracion 0012_company_id_multitenant_tpv_invoice.py usa la funcion
create_foreign_key de Alembic fuera de un bloque batch_alter_table, algo
que SQLite no soporta sin modo batch, y alembic env.py NO activa
render_as_batch=True en context.configure (confirmado leyendo
backend alembic env.py, funcion run_migrations_online, lineas 68-90). El
ciclo se detiene ahi; 0013 a 0053 nunca llegan a ejecutarse en un intento
real desde cero.

Para acotar si habia MAS errores estructurales ademas de este limite de
dialecto conocido, repeti la ejecucion con dos parches de compatibilidad
puramente de prueba (fuera del repositorio, sin tocar ningun fichero de la
rama): (1) omitir la creacion de la constraint FK en SQLite (SQLite no
aplica FKs por defecto de todos modos), y (2) traducir la funcion now() de
PostgreSQL a CURRENT_TIMESTAMP. Con ambos parches aplicados:

0011 -> 0012 ... 0022 -> 0023 -> sqlite3.OperationalError: near "(": syntax error
SQL fallido: CREATE TABLE chat_messages con created_at DATETIME DEFAULT now() NOT NULL

Un segundo bug independiente: alembic versions 0023_chat_messages.py linea
27 usa server_default con el texto now(), sintaxis valida solo en
PostgreSQL, invalida en SQLite. Con el parche tambien aplicado a este
caso, el resto de la cadena (0024 hasta 0053, incluyendo las migraciones
mas recientes y mas relevantes para esta consolidacion: 0043 a 0053,
THALOS, company_id, onboarding-facturacion) SI aplica limpiamente, sin
ningun otro error. Confirme ademas reversibilidad real de las ultimas 5:
downgrade de 0053 a 0048 y upgrade de 0048 a 0053 de vuelta, ambos exitosos.

Contexto importante (verificado con git log, no asumido): ambas
migraciones problematicas (0012, creada en abril 2026; 0023) YA EXISTIAN
EN main version 97b949a antes de que arrancara esta consolidacion - no
fueron introducidas por ninguna de las 9 ramas fusionadas ni por los 3
commits de cierre posteriores. Ademas, ambos fallos son especificos del
dialecto SQLite: la funcion now() es sintaxis nativa valida de PostgreSQL,
y anadir una restriccion de clave foranea via ALTER TABLE es una operacion
estandar soportada de forma nativa por PostgreSQL (a diferencia de
SQLite). Es decir, es probable que contra un PostgreSQL real (el motor de
produccion, segun Railway) esta cadena si aplicara sin los errores que vi
aqui - pero NO PUDE VERIFICARLO: no hay ninguna instancia de PostgreSQL
disponible en este entorno (confirme que no existen los binarios de
PostgreSQL ni Docker en el PATH real, pese a una entrada de PATH heredada
que apunta a una ruta de PostgreSQL inexistente).

Por que esto es un hallazgo real y no un "ya lo sabiamos": ninguno de los
documentos previos (CONSOLIDACION_FINAL.md, ni ningun AUDIT en esta rama)
registra haber ejecutado jamas un alembic upgrade head real desde una base
vacia - la afirmacion de 53 revisiones, una sola cabeza, cero duplicados
se verifico siempre por analisis estatico (grep del campo revision en cada
fichero), nunca por ejecucion. El propio flujo de desarrollo de esta
sesion (confirmado leyendo backend app db base.py, funcion create_tables,
lineas 71-133) usa Base.metadata.create_all para levantar el entorno de
pruebas local, NO Alembic - por eso ningun test ni ninguna verificacion
manual de esta larga sesion de consolidacion paso nunca por este camino, y
por eso esta incompatibilidad (probablemente presente desde abril 2026)
nunca se detecto hasta esta revision.

Que falta para cerrar este punto:

1. Ejecutar alembic upgrade head desde una base vacia contra un PostgreSQL
real desechable (staging de Railway, o un contenedor Docker local) y
confirmar que aplica sin error - esto es lo unico que puede confirmar de
verdad que las 53 mas revisiones aplican limpiamente, ya que el entorno de
produccion real es PostgreSQL, no SQLite.

2. Independientemente del resultado en Postgres, seria conveniente (no
bloqueante para produccion si el punto 1 sale bien, pero si para la
higiene de desarrollo local y CI) envolver la migracion 0012 en un bloque
batch_alter_table para las llamadas create_foreign_key, y sustituir el
server_default de texto now() en la migracion 0023 chat_messages.py
(linea 27) por sa.func.now() de SQLAlchemy, que es dialecto-agnostico (se
traduce correctamente a CURRENT_TIMESTAMP en SQLite y a now() en
Postgres), para que el ciclo completo sea reproducible en SQLite tambien.

---

## 4. Suite completa de tests

Ejecutado por mi, desde cero, venv compartido en backend venv Scripts
python.exe, sobre el codigo actual de feature/consolidacion-final:

cd backend && python -m pytest tests -q
...
7 failed, 300 passed, 34 warnings, 3 errors in 162.19s

Coincide EXACTAMENTE (mismo recuento, mismos 7 nombres de fallo, mismos 3
errores) con lo que reporta AUDIT_JUSTICIA_ESTADO_FINAL.md como estado
final de la rama. No hay discrepancia: es la cifra real, reproducible,
verificada por mi de forma independiente, no copiada de ningun documento.

Fallos (todos preexistentes, no relacionados con los cambios de esta
consolidacion - confirmado por nombre y por causa documentada en los
propios reportes):
- test_basic.py test_config_loading
- test_justicia_control_layer_v1.py test_default_flags_simulated
- test_perseo_autofix_v2.py test_audit_includes_ai_modules
- test_thalos_control_layer_v1.py test_default_mode_is_simulation_for_heuristic_modules
- test_thalos_control_layer_v1.py test_backup_requires_execution_and_backup_flags
- test_thalos_control_layer_v1.py test_build_metadata_origin_mock
- test_thalos_safe_v1.py test_monitoring_cycle_respects_flags
- Errores: test_app.py test_health_check, test_root_endpoint, test_favicon
(NameError: TestClient no definido)

Sin regresion.

---

## 5. Muestreo de frontend (Playwright real, este worktree)

Problema de entorno confirmado y evitado: la herramienta de preview con un
nombre de configuracion lee el archivo launch.json del checkout PRINCIPAL
(ZEUS-IA .claude launch.json), no el de este worktree - confirmado al ver
que ofrecia las configuraciones zeus-frontend y zeus-backend pese a haber
creado mi propia configuracion en el launch.json de este worktree. Para
evitar servir el checkout compartido, arranque vite manualmente con Bash
desde el directorio frontend de este worktree en un puerto aislado (5231)
y use la herramienta de preview con una URL explicita en vez del nombre de
configuracion. Confirme el marcador unico de este commit antes de fiarme
de nada: busque en el codigo fuente servido por el propio vite el
comentario del fix de shouldShowTPV (presente solo en este commit) y lo
encontre, confirmando que estaba sirviendo el codigo correcto.

Backend levantado en puerto 8000 con la variable de entorno
ZEUS_ADDITIONAL_CORS_ORIGINS apuntando al puerto de prueba (para permitir
el origen de prueba via el mecanismo ya soportado por la configuracion del
backend, sin tocar codigo).

### Pantalla 1 - Onboarding

Login real (frontend.reviewer@gmail.com, registrado en esta sesion) ->
redirigido automaticamente a la pantalla de configuracion inicial
(confirma setup_completed false recien registrado, igual que en el
backend). Rellene el formulario paso 1 (empleado, telefono, horario) por
UI real; al enviar sin telefono, aparecio el error de validacion real
"Falta el telefono del empleado 1" (no un stub); al completarlo, avanzo al
paso 2 (cuenta bancaria IBAN para cobros). Sin errores de consola nuevos.

### Pantalla 2 - Dashboard

Con onboarding completado via API para agilizar, navegue al dashboard:
cargo con KPIs reales (Agentes: 6, Tareas 24h: 0, Eficiencia: 0%, etc.).
Cero apariciones del error de referencia shouldShowTPV en la consola (el
bug que motivo el fix de hallazgos-visuales) - confirmado leyendo el log
completo de consola tras la carga. Unico error nuevo: una imagen de
avatar de PERSEO con 404 (cosmetico, no funcional).

### Pantalla 3 - TPV

Cargo la pantalla de TPV Universal Enterprise con datos reales. Accion
real ejecutada: clic en el boton de modo mesas -> cambio a modo ver
productos y disparo llamadas PATCH reales contra el backend (confirmado
en el listado de peticiones de red con respuesta 200 OK), no una
simulacion de interfaz.

### Pantalla 4 (bonus) - Seguros

Cargo la pantalla de Seguros Multirriesgo con listado de polizas vacio
real. Clic en nueva poliza -> formulario real que dispara una peticion al
backend para poblar el selector de cliente - confirma que no es un
formulario estatico.

En las 4 pantallas: sin errores de consola de la aplicacion (solo el 404
cosmetico de un avatar), todas las acciones probadas dispararon llamadas
de red reales contra el backend (no simulaciones de frontend).

---

## Resumen ejecutivo y veredicto

| Punto | Resultado de mi verificacion independiente |
|---|---|
| 1. Los 4 hallazgos criticos | Confirmados los 4, con pruebas propias (multi-tenant real incluido, no solo por HTTP sino con insercion de datos distintivos) |
| 2. Los 6 agentes | Confirmados los 6 - 4 ya establecidos con spot-check propio, PERSEO Google Ads con fallo honesto reproducido en codigo, JUSTICIA con las 2 correcciones nuevas verificadas end-to-end |
| 3. Migraciones Alembic | Estructura correcta (53 revisiones, 1 cabeza, 0 duplicados) PERO la ejecucion real de upgrade head desde cero FALLA en el unico motor disponible en este entorno (SQLite), por dos bugs de compatibilidad de dialecto preexistentes (no introducidos por esta consolidacion) que nunca se habian ejecutado de verdad hasta ahora. No verificable contra PostgreSQL real (no disponible en este entorno) |
| 4. Suite de tests | Confirmado: 7 failed, 300 passed, 34 warnings, 3 errors, exactamente igual a lo documentado, sin regresion |
| 5. Frontend | Confirmado: 4 pantallas cargan sin errores de aplicacion en consola, con acciones reales verificadas contra el backend, usando el codigo de ESTE commit (marcador unico confirmado) |

### Veredicto: DEVUELTO

No por ningun fallo en la logica de negocio, seguridad o aislamiento
multi-tenant del nucleo - los 4 hallazgos criticos, los 6 agentes y las 2
correcciones nuevas de JUSTICIA y PERSEO estan genuinamente resueltos y
los verifique yo mismo con pruebas independientes que en todos los casos
coincidieron con lo reportado.

Se devuelve exclusivamente por el punto 3: la tarea exigia explicitamente
confirmar que las 53 mas revisiones aplican limpiamente sin error en un
ciclo real de alembic upgrade head desde una base vacia, y esa
verificacion NO SE PUEDE DAR POR BUENA - de hecho, al ejecutarla de
verdad (por primera vez en toda esta sesion de consolidacion, segun la
evidencia de que solo se habia hecho analisis estatico hasta ahora) el
ciclo falla dos veces antes de llegar ni siquiera a la migracion 0013.

Que necesito para aprobar en la siguiente vuelta (cualquiera de las dos basta):

1. Evidencia de un alembic upgrade head real, desde una base vacia,
ejecutado contra una instancia de PostgreSQL de verdad (Railway staging
descartable o Docker local) - con salida completa (log de las 53
revisiones) pegada como evidencia. Si aplica limpiamente ahi, el hallazgo
de SQLite pasa a ser un problema de higiene de entorno de desarrollo local
(no bloqueante para produccion), y bastaria con documentarlo asi
explicitamente.

2. Alternativamente, si se prefiere que el ciclo tambien sea reproducible
en SQLite (recomendable para que futuras sesiones de consolidacion puedan
volver a ejecutar esta prueba sin depender de Postgres): envolver la
migracion 0012 en un bloque batch_alter_table para las llamadas
create_foreign_key, y sustituir el server_default de texto now() en la
migracion 0023 chat_messages.py (linea 27) por sa.func.now(), y volver a
probar el ciclo completo desde cero.

No se ha tocado main, no se ha hecho push, no se ha creado ninguna rama
nueva. Este documento se commitea en feature/consolidacion-final.

---

## 6. Fix del hallazgo de la seccion 3 - migraciones Alembic (ejecutor-produccion)

**Rol**: ejecutor-produccion (agente separado del revisor-independiente que
escribio la seccion 3). **Rama**: feature/consolidacion-final (worktree
`consolidacion-final`, sin rama nueva, sin push, sin tocar main).

### 6.1 Diagnostico exacto

El hallazgo original de la seccion 3 documentaba 2 migraciones rotas para
SQLite (0012 y 0023). Al aplicar el primer parche y reintentar el
`alembic upgrade head` desde una base vacia, aparecieron **6 fallos mas en
cascada** con el mismo patron de incompatibilidad de dialecto (no
reportados antes porque la cadena se detenia en 0012, mucho antes de
llegar a ellos). En total, 8 archivos con el problema:

| # | Archivo | Problema exacto |
|---|---|---|
| 1 | `0012_company_id_multitenant_tpv_invoice.py` | 3x `op.create_foreign_key()` fuera de `batch_alter_table` (tpv_products, tpv_sales, invoices). SQLite no soporta `ALTER TABLE ADD CONSTRAINT`. |
| 2 | `0016_document_approvals_workspace_company.py` | 1x `op.create_foreign_key()` fuera de batch (document_approvals). |
| 3 | `0018_employee_work_sessions.py` | `op.add_column()` con `sa.ForeignKey(...)` inline sobre una columna que ya existe en tpv_sales (tabla creada en migraciones previas) - SQLite rechaza anadir una FK via ALTER, incluso via `ForeignKey` inline dentro de `add_column`. |
| 4 | `0021_crm_office.py` | 2x `op.create_foreign_key()` fuera de batch (customers.company_id, customers.owner_user_id). |
| 5 | `0023_chat_messages.py` | `server_default=sa.text("now()")` en `created_at` dentro de `op.create_table()` - `now()` es sintaxis nativa de PostgreSQL, invalida en SQLite (`sqlite3.OperationalError: near "(": syntax error`). |
| 6 | `0043_agent_activities_company_id.py` | `downgrade()`: `op.drop_column("agent_activities", "company_id")` directo tras haber creado la tabla (en instalaciones sin `create_all` previo) con la FK embebida en el propio `CREATE TABLE` - SQLite rechaza el `DROP COLUMN` directo cuando la columna participa en una FK de la definicion original de la tabla. |
| 7 | `0048_products_company_id_tenant_isolation.py` | 2x `op.create_foreign_key()` fuera de batch (products.company_id, products.created_by). |
| 8 | `0050_invoice_tpv_sale_link.py` | `op.add_column()` con `sa.ForeignKey(...)` inline + `op.create_unique_constraint()` fuera de batch (invoices.tpv_sale_id). El `downgrade()` ademas usaba `try/except: pass` para silenciar errores de constraint ya inexistente, en vez de comprobar su existencia real. |

En los 8 casos el patron de fondo es el mismo: **PostgreSQL soporta
`ALTER TABLE ADD/DROP CONSTRAINT` de forma nativa; SQLite no**, y
`backend/alembic/env.py` (funcion `run_migrations_online`, lineas 68-90)
no activa `render_as_batch=True` en `context.configure(...)`, por lo que
cada operacion de constraint debe envolverse explicitamente en
`op.batch_alter_table(...)` migracion por migracion.

### 6.2 Fix aplicado (mismo patron en los 8 archivos)

- Toda llamada a `op.create_foreign_key()` / `op.create_unique_constraint()`
  / `op.drop_constraint()` / `op.drop_column()` que participa en una FK se
  movio dentro de un bloque `with op.batch_alter_table("<tabla>") as batch_op:`,
  usando `batch_op.<metodo>(...)` (sin el nombre de tabla como primer
  argumento, que batch ya conoce por contexto).
- `0018` y `0050`: se separo el `add_column()` con `sa.ForeignKey(...)`
  inline en dos pasos dentro del mismo batch: `batch_op.add_column(sa.Column(...))`
  sin FK inline, seguido de `batch_op.create_foreign_key(...)` explicito con
  nombre de constraint propio (`fk_tpv_sales_work_session_id`,
  `fk_invoices_tpv_sale_id`) - esto ademas corrige un problema latente
  independiente: las FK inline de SQLAlchemy generadas por `add_column`
  quedan sin nombre explicito, dificultando su `DROP` posterior en
  Postgres.
- `0023`: `sa.text("now()")` -> `sa.func.now()`. Verificado que
  `sa.func.now()` es dialecto-agnostico (ver evidencia 6.3.4): compila a
  `CURRENT_TIMESTAMP` en SQLite y a `now()` en PostgreSQL. Es el mismo
  patron ya usado en ~30 migraciones existentes del proyecto (0007, 0008,
  0010, 0011, 0025-0042, 0046, 0049), por lo que 0023 pasa a ser
  consistente con el resto del repositorio en vez de una excepcion.
- `0043` (downgrade): se envolvio el `drop_column("company_id")` (y el
  `drop_constraint` condicional para no-SQLite) en `batch_alter_table`,
  con comentario explicando por que hace falta incluso cuando la FK nunca
  se creo via `ALTER` (puede haber quedado embebida en el `CREATE TABLE`
  original, rama usada cuando `agent_activities` no existia todavia).
- `0050` (downgrade): se elimino el `try/except: pass` que silenciaba
  errores de constraints inexistentes (viola la regla de "no
  simulaciones/manejo de errores real" de la skill zeus-produccion) y se
  sustituyo por una comprobacion real de existencia via
  `inspector.get_indexes()` / `get_unique_constraints()` / `get_foreign_keys()`
  antes de intentar el `drop_constraint`/`drop_index` correspondiente.
- Todos los `downgrade()` correspondientes se revisaron y corrigieron en
  paralelo con el mismo patron batch, para mantener la reversibilidad real
  (no solo el `upgrade()`).

Cambio de comportamiento en PostgreSQL: **ninguno**. `batch_alter_table`
con `recreate="auto"` (el valor por defecto, sin especificar) solo activa
la estrategia de copia de tabla en SQLite; en el resto de dialectos
(incluido PostgreSQL) emite las mismas sentencias `ALTER TABLE` estandar
que las llamadas directas que sustituye - confirmado leyendo el docstring
oficial de `Operations.batch_alter_table` instalado en el venv (alembic
1.13.1, ver evidencia 6.3.5). No se introduce ninguna regresion silenciosa
en produccion.

### 6.3 Evidencia de verificacion (ejecutada por mi, desde cero)

**6.3.1 - Estado del working tree al empezar** (cambios ya presentes sin
commitear, heredados de un ejecutor anterior cortado por limite de
sesion, revisados linea por linea antes de aceptarlos):

```
git status
  modified: backend/alembic/versions/0012_company_id_multitenant_tpv_invoice.py
  modified: backend/alembic/versions/0016_document_approvals_workspace_company.py
  modified: backend/alembic/versions/0018_employee_work_sessions.py
  modified: backend/alembic/versions/0021_crm_office.py
  modified: backend/alembic/versions/0023_chat_messages.py
  modified: backend/alembic/versions/0043_agent_activities_company_id.py
  modified: backend/alembic/versions/0048_products_company_id_tenant_isolation.py
  modified: backend/alembic/versions/0050_invoice_tpv_sale_link.py
```

**6.3.2 - `alembic upgrade head` desde una base SQLite completamente
vacia y desechable** (fuera del repositorio, `DATABASE_URL` apuntando a
`.../scratchpad/ejecutor_migtest_<timestamp>.db`, venv compartido
`backend/venv/Scripts/alembic.exe`):

```
alembic upgrade head
INFO  Running upgrade  -> 0001, Initial migration
...
INFO  Running upgrade 0011 -> 0012, ZEUS_MULTITENANT_MIGRATION_SAFE_001: company_id on tpv_products, tpv_sales, invoices
...
INFO  Running upgrade 0022 -> 0023, Persistencia de mensajes de chat.
...
INFO  Running upgrade 0052 -> 0053, Row Level Security (PostgreSQL) para las 4 tablas de logs de THALOS

alembic current -> 0053 (head)
alembic heads   -> 0053 (head)
```

Las 53 revisiones aplicaron sin ningun error, incluidas las dos que
fallaban en la seccion 3 (0012, 0023) y las 6 adicionales descubiertas
en esta pasada (0016, 0018, 0021, 0043, 0048, 0050).

**6.3.3 - Ciclo `downgrade`/`upgrade` completo** (no solo un muestreo:
downgrade continuo desde 0053 hasta 0011, es decir, la reversa de las 42
migraciones 0012-0053 incluidas las 8 tocadas, seguido de `upgrade head`
de vuelta):

```
alembic downgrade 0011
INFO  Running downgrade 0053 -> 0052, ...
...
INFO  Running downgrade 0012 -> 0011, ZEUS_MULTITENANT_MIGRATION_SAFE_001...
alembic current -> 0011

alembic upgrade head
INFO  Running upgrade 0011 -> 0012, ...
...
INFO  Running upgrade 0052 -> 0053, ...
alembic current -> 0053 (head)
```

Sin ningun error en ninguna direccion. Reversibilidad real confirmada
para las 8 migraciones tocadas (y para todo lo que hay entre medias).

**6.3.4 - `sa.func.now()` es dialecto-agnostico** (verificado compilando
la misma columna contra ambos dialectos con SQLAlchemy, sin necesidad de
una instancia real de Postgres):

```python
col = sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())
CreateColumn(col).compile(dialect=sqlite.dialect())     -> created_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
CreateColumn(col).compile(dialect=postgresql.dialect()) -> created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
```

**6.3.5 - `batch_alter_table` con `recreate="auto"` no cambia el
comportamiento en PostgreSQL** (docstring oficial de
`alembic.operations.Operations.batch_alter_table`, alembic 1.13.1
instalado en el venv):

> "recreate": under what circumstances the table should be recreated.
> At its default of "auto", the SQLite dialect will recreate the table
> if any operations other than add_column(), create_index(), or
> drop_index() are present. [...] The batch operation on other backends
> will proceed using standard ALTER TABLE operations.

**6.3.6 - Suite completa de tests, sin regresion** (venv compartido,
BD de desarrollo normal del worktree, `backend/zeus.db`):

```
cd backend && python -m pytest tests -q
...
7 failed, 300 passed, 34 warnings, 3 errors in 183.11s (0:03:03)
```

Mismos 7 nombres de fallo y mismos 3 errores que el baseline documentado
en la seccion 4 de este mismo documento (`test_config_loading`,
`test_default_flags_simulated`, `test_audit_includes_ai_modules`,
`test_default_mode_is_simulation_for_heuristic_modules`,
`test_backup_requires_execution_and_backup_flags`,
`test_build_metadata_origin_mock`, `test_monitoring_cycle_respects_flags`;
errores en `test_health_check`, `test_root_endpoint`, `test_favicon` por
`NameError: TestClient no definido`, preexistente y documentado). Sin
regresion.

**6.3.7 - Limpieza de bases de datos desechables**: se elimino la base
SQLite de prueba creada para 6.3.2/6.3.3 (fuera del repositorio, en
`scratchpad`), y se eliminaron dos artefactos `.db` sueltos que habian
quedado en el worktree de sesiones de revision anteriores
(`backend/zeus_reviewer_frontend.db`, `backend/zeus_reviewer_test.db`,
ambos vacios) y una `zeus.db` residual en la raiz del worktree (ajena a
`backend/`, ambas ignoradas por git, ninguna es el estado de desarrollo
real). Se conservo intacta `backend/zeus.db` (la base de desarrollo real
usada por el pytest de 6.3.6).

### 6.4 Limitacion que sigue sin poder verificarse en este entorno

Igual que documento la seccion 3: **no hay ninguna instancia de
PostgreSQL disponible en este entorno** (sin binarios de Postgres ni
Docker en el PATH). El fix de esta seccion se limita, por diseno
(`batch_alter_table` con `recreate="auto"`), a no cambiar el SQL emitido
en PostgreSQL - respaldado por el docstring oficial de Alembic (6.3.5) y
por el hecho de que `sa.func.now()` compila a la sintaxis nativa correcta
en ambos dialectos (6.3.4) - pero esto sigue siendo una verificacion por
lectura de codigo y documentacion oficial, no una ejecucion real contra
Postgres. Sigue siendo recomendable, cuando haya acceso a un Postgres de
staging o Docker, ejecutar `alembic upgrade head` una vez desde cero
contra el como confirmacion final independiente de este razonamiento.

### 6.5 Veredicto de este step

No me autodeclaro aprobado. Este documento y el commit correspondiente
quedan listos para la verificacion de `revisor-independiente`, que es
quien decide si el hallazgo de la seccion 3 queda cerrado.

Resumen para el revisor: los 8 archivos ahora usan de forma consistente
`batch_alter_table` para toda operacion de constraint sobre SQLite y
`sa.func.now()` en vez de `now()` literal; `alembic upgrade head` desde
cero (53 revisiones) y el ciclo `downgrade`/`upgrade` completo (0053 a
0011 y de vuelta) se ejecutaron sin error; la suite de tests no tiene
regresion (7 failed, 300 passed, 3 errors, identico al baseline);
PostgreSQL real sigue sin poder probarse en este entorno, limitacion ya
conocida y ahora acotada con evidencia adicional (docstring oficial +
compilacion de columna por dialecto) de que el fix no deberia alterar el
comportamiento alli.

---

## 7. Verificacion independiente del fix de la seccion 6 y veredicto final de toda la consolidacion

**Rol**: revisor-independiente (mismo rol que escribio las secciones 1-5 y el
veredicto DEVUELTO original). **Metodologia**: cero confianza en lo escrito en
la seccion 6 por ejecutor-produccion - cada afirmacion se repitio con
herramientas propias, una base SQLite desechable nueva (nunca usada antes,
creada y borrada en esta sesion, fuera del repositorio), un pytest propio y
lectura directa del diff del commit 9fb22c2.

### 7.1 Diff de las 8 migraciones - lectura completa, linea por linea

Lei el diff completo de "git show 9fb22c2" para los 8 archivos
(0012, 0016, 0018, 0021, 0023, 0043, 0048, 0050). Confirmado:

- El patron es identico y consistente en los 8 archivos: toda llamada a
  create_foreign_key / create_unique_constraint / drop_constraint /
  drop_column que participa en una FK se movio dentro de
  "with op.batch_alter_table(tabla) as batch_op:", sin cambiar tabla
  origen, columnas, ondelete, ni nombres de constraint.
- 0018 y 0050: el add_column con ForeignKey inline se separo en
  batch_op.add_column(sa.Column(...)) (sin FK) + batch_op.create_foreign_key(...)
  explicito - confirmado que el resultado final (columna + FK con el mismo
  ondelete) es equivalente, solo cambia la sintaxis de creacion.
- 0023: unico cambio es sa.text("now()") a sa.func.now() en la columna
  created_at de chat_messages, ninguna otra linea tocada.
- 0043 downgrade: se envolvio el drop_column/drop_constraint existente en
  batch; la logica condicional "if bind.dialect.name != sqlite" para la FK ya
  existia antes del fix (no se toco), confirmado leyendo el archivo completo
  (no solo el diff).
- 0050 downgrade: el try/except: pass que silenciaba errores de
  constraints inexistentes se sustituyo por comprobacion real via
  inspector.get_indexes()/get_unique_constraints()/get_foreign_keys() -
  confirmado que el flujo de datos (que columnas/constraints se borran) es el
  mismo, solo se elimino el manejo de errores por silenciamiento.
- En ningun archivo se toco: nombre de tabla destino, tipo de columna,
  ondelete, orden de operaciones de negocio (backfills, condicionales de
  entorno sin create_all previo en 0043/0048/0050), ni ninguna otra
  migracion fuera de estas 8. Veredicto: cambio puramente de sintaxis DDL,
  sin alteracion de logica de negocio, confirmado.

### 7.2 alembic upgrade head desde una base SQLite vacia - reproducido por mi

Cree mi propia base desechable, con nombre distinto a cualquier archivo usado
en rondas anteriores (reviewer2_migtest_1787856334.db, fuera del
repositorio, en el directorio temporal de esta sesion), confirmando primero
que el archivo NO existia:

```
DATABASE_URL=sqlite:///.../reviewer2_migtest_1787856334.db
alembic upgrade head
INFO  Running upgrade  -> 0001, Initial migration
...
INFO  Running upgrade 0011 -> 0012, ZEUS_MULTITENANT_MIGRATION_SAFE_001...
...
INFO  Running upgrade 0022 -> 0023, Persistencia de mensajes de chat.
...
INFO  Running upgrade 0052 -> 0053, Row Level Security (PostgreSQL) para las 4 tablas de logs de THALOS

alembic current -> 0053 (head)
alembic heads   -> 0053 (head)
```

Las 53 revisiones aplicaron sin ningun error, incluidas las dos que fallaban
en la seccion 3 original (0012, 0023) y las 6 adicionales de la seccion 6
(0016, 0018, 0021, 0043, 0048, 0050). Confirmado con mi propio entorno, no
reutilizando ningun archivo de sesiones anteriores.

### 7.3 Ciclo downgrade/upgrade - reproducido por mi (mismo punto de corte que el ejecutor, 0011)

Sobre la misma base recien creada:

```
alembic downgrade 0011
INFO  Running downgrade 0053 -> 0052, ...
...
INFO  Running downgrade 0012 -> 0011, ZEUS_MULTITENANT_MIGRATION_SAFE_001...
alembic current -> 0011   (confirmado)

alembic upgrade head
INFO  Running upgrade 0011 -> 0012, ...
...
INFO  Running upgrade 0052 -> 0053, ...
alembic current -> 0053 (head)   (confirmado)
```

Sin ningun error en ninguna direccion. Reversibilidad real confirmada de
forma independiente.

### 7.4 sa.func.now() dialecto-agnostico - verificado y ademas comparado directamente contra el sa.text("now()") original

Compile la misma columna con SQLAlchemy contra ambos dialectos:

```
SQLite:     created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL
PostgreSQL: created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
```

Fui un paso mas alla que el ejecutor: compile tambien una columna con el
sa.text("now()") ORIGINAL (el que tenia 0023 antes del fix) contra
PostgreSQL para comparar directamente:

```
PG con sa.func.now():      created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
PG con sa.text("now()"):   created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
```

Salida SQL identica caracter por caracter en PostgreSQL entre la version
anterior y la nueva. Esto es una confirmacion mas concluyente que la
compilacion aislada: no solo "es dialecto-agnostico" en abstracto, sino que
para este caso concreto el SQL emitido en produccion (Postgres) no cambia en
absoluto. Cero riesgo de regresion silenciosa en Postgres por este cambio.

Adicionalmente verifique el docstring oficial de
alembic.operations.base.Operations.batch_alter_table (alembic 1.13.1,
mismo venv) y confirme la cita textual: "The batch operation on other
backends will proceed using standard ALTER TABLE operations." - coincide
exactamente con lo afirmado en la seccion 6.2.

### 7.5 Suite completa de tests - reproducida por mi, venv compartido, BD de desarrollo del worktree

```
cd backend && python -m pytest tests -q
...
FAILED tests/test_basic.py::test_config_loading
FAILED tests/test_justicia_control_layer_v1.py::test_default_flags_simulated
FAILED tests/test_perseo_autofix_v2.py::test_audit_includes_ai_modules
FAILED tests/test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules
FAILED tests/test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags
FAILED tests/test_thalos_control_layer_v1.py::test_build_metadata_origin_mock
FAILED tests/test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags
ERROR tests/test_app.py::test_health_check - NameError: name 'TestClient' is not defined
ERROR tests/test_app.py::test_root_endpoint - NameError: name 'TestClient' is not defined
ERROR tests/test_app.py::test_favicon - NameError: name 'TestClient' is not defined
7 failed, 300 passed, 34 warnings, 3 errors in 154.98s (0:02:34)
```

Identico en numero y en cada nombre de fallo/error al baseline documentado en
la seccion 4 y reconfirmado en la seccion 6.3.6. Sin regresion.

### 7.6 Limpieza del worktree y estado de main/remoto

- Borre mi propia base desechable (reviewer2_migtest_1787856334.db) al
  terminar; confirmado que ya no existe.
- git status --porcelain sobre el worktree: limpio (sin cambios sin
  commitear).
- Busque *.db en todo el worktree (excluyendo node_modules/venv): solo
  aparecen backend/zeus.db (BD real de desarrollo, usada para el pytest de
  7.5, intencionalmente conservada, ignorada por git) y los backups
  automaticos de THALOS en backend/storage/backups/*.db (feature existente,
  no relacionada con esta tarea, tambien ignorados por git). Ningun artefacto
  .db huerfano de las rondas de revision/ejecucion anteriores
  (zeus_reviewer_test.db, zeus_reviewer_frontend.db,
  ejecutor_migtest_*.db, etc.) permanece en el worktree - confirmado que la
  limpieza declarada en 6.3.7 es real.
- main sigue en 97b949a (no se movio); feature/consolidacion-final sigue
  178 commits por delante de main, sin upstream configurado (no se ha hecho
  push); no se creo ninguna rama nueva.

### 7.7 Veredicto de la seccion 6 (el fix de migraciones)

CONFIRMADO. Las 8 migraciones ahora usan batch_alter_table de forma
consistente y correcta, sin alterar ninguna logica de negocio; alembic
upgrade head desde una base SQLite vacia aplica las 53 revisiones sin error
(reproducido por mi con una base propia, nunca usada antes); el ciclo
downgrade/upgrade completo funciona en ambas direcciones (reproducido por
mi); sa.func.now() no cambia el SQL emitido en PostgreSQL respecto al
sa.text("now()") anterior (confirmado por comparacion directa, no solo por
compilacion aislada); la suite de tests no tiene regresion (7 failed, 300
passed, 3 errors, identico al baseline). El motivo exacto de la devolucion en
la seccion 3 (el alembic upgrade head real desde SQLite vacio fallaba en
0012) queda resuelto de verdad, no solo aparentemente.

### 7.8 Veredicto final de TODA la rama feature/consolidacion-final

Con este cierre, los cinco puntos que exigia la revision independiente quedan
todos CONFIRMADOS con pruebas propias, repetidas de cero en esta sesion y en
la sesion anterior:

1. Los 4 hallazgos criticos historicos (dashboard multi-tenant, invoices/
   products/customers, endpoints Google, onboarding sin 500 de doble sesion):
   confirmados con pruebas propias en la ronda anterior.
2. Los 6 agentes (ZEUS, THALOS, RAFAEL, AFRODITA, PERSEO, JUSTICIA),
   incluidas las correcciones nuevas de JUSTICIA (handler real + fuga
   multi-tenant en compliance_events) y el fallo honesto de PERSEO Google
   Ads: confirmados con pruebas propias en la ronda anterior.
3. Migraciones Alembic: estructura correcta y, tras el fix de esta ronda,
   ejecucion real alembic upgrade head desde cero TAMBIEN confirmada
   (53/53 revisiones, sin error, reversibilidad completa) - punto que motivo
   la devolucion, ahora cerrado con pruebas propias.
4. Suite de tests: 7 failed, 300 passed, 34 warnings, 3 errors, reproducido
   de forma identica en ambas rondas, sin regresion en ningun momento.
5. Frontend: 4 pantallas verificadas con Playwright real en la ronda
   anterior, sin errores de aplicacion en consola, con acciones reales contra
   el backend.

### VEREDICTO: APROBACION DEFINITIVA de feature/consolidacion-final

No quedan puntos abiertos que bloqueen produccion. Se aprueba la rama
completa (176+ commits originales, 9 ramas fusionadas, mas 3 commits de
cierre puntuales de seguridad/migraciones posteriores, mas este commit de
verificacion) para su fusion a main y despliegue.

Resumen ejecutivo de que contiene esta rama:

- Nucleo multi-tenant real: aislamiento por company_id verificado en
  metrics/dashboard, invoices, products, customers, agent_activities,
  compliance_events, con pruebas de fuga cruzada negativas en todos los
  casos probados.
- THALOS como middleware obligatorio: 401 real sin token en todos los
  endpoints probados (metrics, invoices, products, customers, google/*,
  justice/*), registro real de intentos de login (exito y fallo) en
  thalos_login_attempts.
- Los 6 agentes con logica real y logging verificable: ZEUS (orquestador),
  THALOS (seguridad), RAFAEL (gastos/fiscal), AFRODITA (inventario/RRHH,
  con su propio modo SIMULATED declarado honestamente donde el flag de
  escritura real aun no esta activado), PERSEO (Google Ads con fallo
  honesto 501/503, sin exito falso), JUSTICIA (automatizacion real +
  aislamiento multi-tenant en compliance).
- Onboarding sin el 500 de doble sesion historico, con ciclo completo
  cuestionario -> setup_completed verificado.
- 53 migraciones Alembic, una sola cabeza, sin duplicados, y ahora tambien
  ejecutables de verdad desde cero en SQLite (antes solo se habia verificado
  por analisis estatico) y reversibles.
- Suite de tests estable: 300 passed, 7 failed y 3 errors preexistentes y
  documentados (no relacionados con ningun cambio de esta consolidacion).
- Frontend funcional en las 4 pantallas muestreadas (onboarding, dashboard,
  TPV, seguros), con llamadas reales al backend, sin regresiones visuales
  del bug historico shouldShowTPV.

Pendiente como tareas separadas para el futuro (no bloqueante para este
cierre, documentado explicitamente para que no se pierda):

1. Ejecutar alembic upgrade head desde una base vacia contra una instancia
   de PostgreSQL real (Railway staging descartable o Docker local) en cuanto
   haya un entorno disponible, como confirmacion final independiente de que
   el fix de la seccion 6 (y el resto de las 53 migraciones) aplica tambien
   alli sin error - la evidencia actual (docstring oficial de alembic +
   compilacion de columna identica en Postgres antes/despues del cambio) es
   solida pero sigue siendo analisis, no ejecucion real contra Postgres.
2. Verificar Row Level Security (migraciones 0047 y 0053, especificas de
   PostgreSQL) contra una instancia Postgres real - en SQLite estas
   migraciones son no-op por diseno (RLS no existe en SQLite), por lo que el
   ciclo SQLite verificado en esta sesion no prueba nada sobre el
   comportamiento real de RLS.
3. Los 7 tests fallidos y 3 errores preexistentes (nombrados en la seccion
   4/6.3.6/7.5 de este documento) siguen sin corregirse - documentados como
   no relacionados con esta consolidacion, pero deberian resolverse en un
   step propio en vez de arrastrarse indefinidamente.
4. Credenciales AEAT y Google siguen pendientes de configurar en produccion
   (ya documentado como conocido en la skill zeus-produccion, no es un
   hallazgo nuevo).
5. El 404 cosmetico del avatar de PERSEO observado durante el muestreo de
   frontend (seccion 5) - no funcional, pero pendiente de arreglo visual.

No se ha tocado main, no se ha hecho push, no se ha creado ninguna rama
nueva. Este documento y el commit correspondiente se realizan en
feature/consolidacion-final.
