# Auditoría — Onboarding: datos de facturación (CIF/NIF, razón social, IBAN)

Rama: `feature/onboarding-facturacion` (desde `main`). Ningún cambio en `main`, ningún push.

## 0. Corrección post-revisión (revisor-independiente)

`revisor-independiente` devolvió el trabajo original (commit `32b489a`) por un
hallazgo real y serio en `backend/app/core/crypto.py::_resolve_key()`: si
`FIELD_ENCRYPTION_KEY` faltaba en producción, el código solo registraba un
`WARNING` y seguía cifrando/descifrando IBANes con una clave derivada de
`SECRET_KEY` — que a su vez tiene un valor por defecto hardcodeado en
`app/core/config.py:324` que tampoco bloquea el arranque. Combinado, esto
permitía derivar la clave de cifrado del IBAN solo con acceso al código
fuente, sin BD ni variables de entorno reales — la misma clase de fallo que
el incidente de credenciales de esta sesión.

**Corrección aplicada** (más estricta que el mínimo pedido por el revisor):
`_resolve_key()` ahora falla en cerrado (`EncryptionKeyNotConfiguredError`,
subclase de `RuntimeError`) **siempre** que `ENVIRONMENT`/`RAILWAY_ENVIRONMENT`
resuelva a `production` y `FIELD_ENCRYPTION_KEY` no esté configurada — sin
importar el estado de `SECRET_KEY`. El fallback derivado de `SECRET_KEY`
sigue existiendo, pero exclusivamente para `ENVIRONMENT != production`
(desarrollo/tests local), donde nunca hay IBANes reales en juego.

Verificado en vivo reproduciendo exactamente el escenario del revisor
(`ENVIRONMENT=production`, `FIELD_ENCRYPTION_KEY` y `SECRET_KEY` ausentes del
proceso): `encrypt_sensitive_value()` lanza `EncryptionKeyNotConfiguredError`
en vez de cifrar. Con `FIELD_ENCRYPTION_KEY` configurada en producción, el
cifrado/descifrado funciona exactamente igual que antes (probado de nuevo
contra el servidor real vía `GET /onboarding/status` con el IBAN de un
tenant ya guardado, que sigue devolviéndose enmascarado correctamente).
Suite completa repetida tras el cambio: `7 failed, 214 passed, 2 skipped, 3
errors` — mismo baseline, sin regresión. Commit de esta corrección:
ver `git log` en esta rama, mensaje `fix(security): ...`.

## 1. Qué se construyó

### Frontend (`frontend/src/views/OnboardingSetup.vue`)
Se añadieron tres campos nuevos al paso 2 ("Canales") del formulario, en una
sección nueva "Datos de facturación":

1. **Nombre completo / razón social** (`form.legal_name`) — texto libre, requerido.
2. **CIF/NIF de la empresa** (`form.tax_id`) — requerido, con validación de
   formato en tiempo real (`@blur` + computed `taxIdValid`) usando
   `frontend/src/utils/validatorsEs.ts`.
3. **Cuenta bancaria (IBAN)** (`form.iban`) — requerido salvo que ya exista un
   IBAN guardado (en cuyo caso se puede dejar en blanco para conservarlo, o
   rellenar uno nuevo para sustituirlo), con validación de checksum mod-97 en
   tiempo real.

`nextStep()` bloquea el avance del paso 2 si `legal_name` está vacío, si
`tax_id` no pasa `validarNifCif()`, o si `iban` (cuando se rellena) no pasa
`validarIban()`. `onMounted()` recupera `tax_id`, `legal_name` e
`iban_masked` del endpoint de status y los muestra (el IBAN real nunca se
recibe en el frontend, solo la versión enmascarada). El resumen del paso 3
también muestra estos tres campos, enmascarando el IBAN con
`maskIban()` si el usuario introdujo uno nuevo.

Nuevo archivo `frontend/src/utils/validatorsEs.ts`: implementa en TypeScript
el mismo algoritmo que el backend (NIF mod-23, CIF con suma
par/impar + tabla de letras de control, IBAN mod-97) para dar feedback
inmediato — el backend es la fuente de verdad y siempre revalida.

### Backend

- **`backend/app/core/validators_es.py`** (nuevo): `validar_nif`,
  `validar_cif`, `validar_nif_cif`, `validar_iban`, `mask_iban`. Implementa
  los algoritmos reales (no solo regex de longitud):
  - NIF: 8 dígitos, letra de control = `"TRWAGMYFPDXBNJZSQVHLCKE"[numero % 23]`.
  - CIF: letra inicial + 7 dígitos + dígito/letra de control, con la regla
    real de qué letras iniciales exigen dígito (`ABEH`), cuáles exigen letra
    (`KPQS`) y cuáles aceptan ambas (resto).
  - IBAN: reordena `BBAN + código país + dígitos de control`, convierte
    letras a números (A=10..Z=35) y comprueba `mod 97 == 1` (ISO 7064
    MOD 97-10 estándar).
  - `mask_iban`: deja visibles el código de país y los últimos 4 caracteres,
    el resto se sustituye por `*`.

- **`backend/app/schemas/token.py`**: `OnboardingProfileRequest` gana los
  campos `tax_id`, `legal_name`, `iban`, cada uno con un `@validator` que
  invoca los validadores reales de `validators_es.py` y lanza `ValueError`
  (→ HTTP 422) si el formato/checksum es inválido. Esta es la validación de
  verdad — el frontend es solo UX.

- **`backend/app/core/crypto.py`** (nuevo): cifrado simétrico con
  `cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256 autenticado, ya
  presente en `requirements.txt` — no es cifrado casero ni base64
  disfrazado). La clave se deriva de la variable de entorno
  `FIELD_ENCRYPTION_KEY` (nunca hardcodeada). Si no está configurada: en
  producción se registra un `WARNING` de seguridad explícito y se usa un
  fallback derivado de `SECRET_KEY` (mismo patrón que ya existe para
  `SECRET_KEY` en `app/core/config.py`); en desarrollo/tests se usa el mismo
  fallback con un aviso una sola vez. `encrypt_sensitive_value` /
  `decrypt_sensitive_value` son las únicas funciones que tocan el IBAN en
  claro, y ninguna lo loguea.

- **`backend/app/models/company.py`**: nuevas columnas en `Company`:
  `tax_id` (String(20), indexada), `legal_name` (String(255)),
  `iban_encrypted` (Text — el IBAN cifrado, nunca en claro).

- **`backend/app/api/v1/endpoints/auth.py`**:
  - `POST /api/v1/auth/onboarding/profile` (`_onboarding_profile_impl`):
    guarda `tax_id`/`legal_name` tal cual (ya validados por el schema) y, si
    llega `iban`, lo cifra con `encrypt_sensitive_value()` antes de asignarlo
    a `company.iban_encrypted`. Sigue pasando por `get_current_active_user`
    (auth real) y todas las queries de la empresa filtran por
    `UserCompany.user_id == current_user.id` → `company_id` (aislamiento
    multi-tenant ya existente en el endpoint, no se ha tocado ese filtro).
  - `GET /api/v1/auth/onboarding/status`: añade `tax_id`, `legal_name`,
    `iban_masked` (descifrado en memoria solo para enmascarar, nunca se
    envía el valor real) y `has_iban_on_file` a la respuesta.
  - Todo el endpoint ya pasa por `SecurityMiddleware` (registrado
    globalmente en `app/main.py`, aplica a toda la app) — no se ha añadido
    ninguna ruta que lo evite.

### Migración Alembic

`backend/alembic/versions/0043_company_billing_fields.py` (correlativo real:
la última existente era `0042_zeus_domain_events.py`). Añade `tax_id`,
`legal_name`, `iban_encrypted` a `companies` de forma idempotente
(`IF NOT EXISTS` en Postgres, guard por inspección de columnas en SQLite).
`downgrade()` revierte las 3 columnas y el índice.

Además, se añadió `_migrate_company_billing_fields()` en
`backend/app/db/base.py` y se registró en `ensure_schema_patches()`,
siguiendo el mismo patrón ya usado en el proyecto para el resto de columnas
añadidas fuera de un `alembic upgrade head` explícito (Railway/SQLite local
no siempre corren la migración Alembic real antes de arrancar la app; este
parche idempotente es el mecanismo de seguridad ya establecido en el
repo — ver `_migrate_tpv_company_columns`, `_migrate_smart_time_control_tables`,
etc., en el mismo archivo).

## 2. Mecanismo de cifrado: reutilizado vs nuevo

Se buscó primero un patrón existente (`grep -r "cryptography\|Fernet\|encrypt\|cipher" backend/`).
No existía ningún cifrado de campo real en el proyecto — la única coincidencia
de "encryption_status" en `app/core/zeus_agents.py:369` es una cadena de
estado fija sin cifrado real detrás (fuera del alcance de esta tarea, no se
ha tocado). El paquete `cryptography==42.0.5` ya estaba en
`requirements.txt` (usado indirectamente por `python-jose[cryptography]`
para JWT), así que se reutilizó esa dependencia ya instalada en vez de añadir
una nueva, y se implementó `app/core/crypto.py` desde cero siguiendo el
patrón de manejo de secretos por variable de entorno que ya usa
`SECRET_KEY` en `app/core/config.py` (dev fallback + warning, nunca un
literal hardcodeado).

## 3. Verificación — resultado exacto de cada paso

### Baseline de tests (antes de tocar código)
```
cd backend && python -m pytest tests/ -q
7 failed, 214 passed, 2 skipped, 3 errors in 154.41s
```

### Baseline tras los cambios (mismo comando, después de implementar todo)
```
7 failed, 214 passed, 2 skipped, 3 errors in 156.06s
```
Idéntico al baseline — sin regresiones. Los 7 failed / 3 errors preexistentes
no están relacionados con esta tarea (modo simulación de THALOS/JUSTICIA,
`TestClient` no definido en `test_app.py`, etc.).

### Migración Alembic — aplicación aislada
Se creó una BD SQLite de prueba con solo la tabla `companies` (columnas
mínimas) y `alembic_version` estampada en `0042`, y se ejecutó
`alembic upgrade head` apuntando a esa BD:
```
INFO  [alembic.runtime.migration] Running upgrade 0042 -> 0043,
  company_billing_fields — CIF/NIF, razón social e IBAN cifrado para onboarding
```
Verificación de columnas resultantes vía `PRAGMA table_info(companies)`:
`['id', 'company_name', 'slug', 'tax_id', 'legal_name', 'iban_encrypted']` — correcto.

(Nota: `alembic upgrade head` desde una BD SQLite totalmente vacía falla en
una migración muy anterior, `0003`, ajena a este cambio — el proyecto asume
`create_tables()` + `ensure_schema_patches()` para bootstrap de BD nueva y
Alembic para el histórico incremental; ver sección 4.)

### Backend — curl contra servidor real (SQLite local, puerto 8010)

Registro de 3 tenants reales vía `POST /api/v1/auth/register` (usuario +
empresa nuevos cada uno): `onboarding.tenant.a@example.com` (company_id=29),
`onboarding.tenant.b@example.com` (company_id=30),
`onboarding.tenant.c@example.com` (company_id=31).

**Guardado con datos reales y válidos (tenant A):**
```
POST /api/v1/auth/onboarding/profile
  legal_name: "Tenant A Restauracion SL"
  tax_id: "B12345674"   (CIF válido, control dígito calculado)
  iban: "ES9121000418450200051332"  (IBAN real de ejemplo de Wikipedia, mod-97 OK)
→ 200 {"success":true,"company_id":29,...}
```

**Recuperación (GET /api/v1/auth/onboarding/status, tenant A):**
```
"tax_id":"B12345674","legal_name":"Tenant A Restauracion SL",
"iban_masked":"ES** **** **** **** **** 1332","has_iban_on_file":true
```
IBAN devuelto siempre enmascarado, nunca en claro.

**Rechazo de CIF/NIF inválido (backend, no solo frontend):**
```
tax_id: "B12345678" (dígito de control incorrecto)
→ 422 {"detail":[{"type":"value_error","loc":["body","tax_id"],
   "msg":"Value error, CIF/NIF inválido: revisa el formato y la letra/dígito de control", ...}]}
```

**Rechazo de IBAN inválido (backend):**
```
iban: "ES9121000418450200051399" (checksum mod-97 incorrecto)
→ 422 {"detail":[{"type":"value_error","loc":["body","iban"],
   "msg":"Value error, IBAN inválido: revisa el formato y el dígito de control (mod-97)", ...}]}
```

**Caso de error de autenticación (sin token / token inválido):**
```
GET /onboarding/status sin Authorization → 401 {"detail":"No se pudieron validar las credenciales"}
GET /onboarding/status con "Bearer invalid.token.value" → 401 (mismo detail)
```
Falla controladamente (401), no con 500 opaco ni con un falso 200.

### Multi-tenant — aislamiento verificado con 2 tenants reales

Tenant A guardó `tax_id=B12345674`, IBAN terminado en `...1332`. Tenant B
(usuario y empresa distintos) guardó `tax_id=12345678Z`, IBAN GB
(`GB29NWBK60161331926819`, ejemplo real de Wikipedia para Reino Unido,
confirma que el checksum mod-97 no está limitado a IBAN español).
`GET /onboarding/status` con el token de B, **antes** de que B guardara sus
propios datos, devolvió `"tax_id":null,"legal_name":null,"iban_masked":null`
— cero visibilidad de los datos de A. Tras guardar, cada tenant vio
únicamente sus propios valores:
```
Tenant A → tax_id: B12345674   | iban_masked: ES** **** **** **** **** 1332
Tenant B → tax_id: 12345678Z   | iban_masked: GB** **** **** **** **68 19
```

### Query directa a BD — IBAN genuinamente cifrado en reposo

```sql
SELECT id, company_name, tax_id, legal_name, iban_encrypted FROM companies WHERE id IN (29,30,31);
```
```
(29, 'Tenant A Restaurante', 'B12345674', 'Tenant A Restauracion SL',
     'gAAAAABqh2X6lB95-Q-S_FwTLoWXMpDnwk5pZsblxxUu0S9HtCQstTJo9nEHTtQIZnoER-W8PdGffM2rkPwUvKP-pFrAe2g8hrPnJfxHvuDfg9HkA2yywpQ=')
(30, 'Tenant B Oficinas', '12345678Z', 'Tenant B Oficinas SL',
     'gAAAAABqh2Yr8SnHQLgJVW71BBVO3kBJSe4TbCJ90wTmvxsbaw7ap2qPymCoXy2YCTdsLv50KH2GC61SWEibvEb8MEILPiHoOPMPqUPW3HCVw-xMUVnKzRc=')
(31, 'Tenant C Servicios', 'G12345674', 'Tenant C Servicios Digitales SL',
     'gAAAAABqh_2SNPTJr76IrLp42R-W78Q5rzb1RXaK1yuKx-eb2D33hEroVM6CkOvZFq-HX7_BOpwSISaSCSO_rVb5369fDOX47e7VOf_0SOZaV-0JBXw5Z3Y=')
```
`iban_encrypted` es un token Fernet opaco (prefijo `gAAAAAB...`), no una
transformación trivial (mayúsculas/espacios) del IBAN real — es un dato
irreconocible sin la clave. Nótese que el tenant A y el tenant C guardaron el
mismo IBAN en claro (`ES9121000418450200051332`) y el ciphertext resultante
es **distinto** en cada fila (Fernet incluye IV/nonce aleatorio), confirmando
que no es un hash determinista ni una codificación reversible trivial.
También se confirmó (`grep` sobre el log completo del servidor de prueba)
que el IBAN en claro no aparece **en ningún punto** de los logs del proceso
backend durante toda la sesión de pruebas (0 coincidencias).

### Frontend — verificación con Playwright/browser real

Se sirvió el frontend real (`npm run dev`, Vite) desde el propio checkout de
esta rama (con `npm ci` en el worktree para tener `node_modules` reales) y se
condujo el flujo completo en el navegador:

1. Login real como `onboarding.tenant.c@example.com` (tenant C, recién
   registrado) contra el backend real en `http://localhost:8010`.
2. Navegación a `/onboarding-setup`, relleno del paso 1 (empleados, horario)
   y paso 2, incluida la nueva sección "Datos de facturación":
   - Razón social: `Tenant C Servicios Digitales SL`
   - CIF/NIF: `G12345674` (CIF válido, letra inicial admite dígito o letra
     de control, se usó el dígito)
   - IBAN: `ES91 2100 0418 4502 0005 1332` (con espacios, tal y como lo
     escribiría un usuario real)
3. Paso 3 (resumen) mostró el IBAN ya enmascarado en pantalla:
   `ES** **** **** **** 1332` antes incluso de enviar el formulario.
4. Clic en "Finalizar configuración" → `POST /onboarding/profile` real → 200
   OK → redirección a `/dashboard`.
5. Recarga de `/onboarding-setup`: el paso 2 recuperó `Razón social` y
   `CIF/NIF` pre-rellenados desde el backend, y mostró el aviso
   `IBAN ya guardado: ES** **** **** **** 1332. Déjalo en blanco para
   mantenerlo, o introduce uno nuevo para sustituirlo.` — el IBAN real nunca
   llegó al navegador.
6. Validación de cliente en vivo: se introdujo un CIF con dígito de control
   incorrecto (`G12345678`) → apareció de inmediato "CIF/NIF con formato
   inválido (revisa dígitos y letra de control)." y el botón "Siguiente" no
   avanzó de paso mientras el error persistía. Se restauró el valor válido
   para dejar el registro de prueba consistente.

**Nota metodológica**: dado que esta tarea se ejecutó en un *worktree* git
aislado, el `preview_start` con nombre de configuración (`.claude/launch.json`)
apunta al checkout compartido, no a este worktree — se usaron en su lugar
instancias de `npm run dev` / `uvicorn` lanzadas manualmente dentro del
worktree, en puertos no conflictivos (8010, 5183/5184), y `preview_start`
con parámetro `url` para adjuntar el pane del navegador a esas instancias.
Se ajustó temporalmente la CSP de `index.html` y se usó la variable de
entorno ya existente `ZEUS_ADDITIONAL_CORS_ORIGINS` para permitir esos
puertos de prueba; **ambos ajustes se revirtieron antes de comitear**
(`git diff frontend/index.html` contra `main` está vacío). También se
neutralizó temporalmente (con comentario `TEMP_TEST_DISABLE_REDIRECT`) el
redirect automático de `OnboardingSetup.vue` a `/dashboard` cuando
`setup_completed` ya es `true` — necesario porque el registro de un tenant
nuevo ya deja `setup_inferred=true` por heurística preexistente (ver
hallazgo en sección 4) y sin este ajuste temporal la página nunca es
alcanzable para probar el formulario. Este cambio también se revirtió antes
de comitear.

## 4. Limitaciones y hallazgos (no corregidos en este cambio, fuera de alcance)

1. **Heurística de "setup_inferred" oculta el formulario de onboarding para
   casi todos los usuarios nuevos.** `GET /onboarding/status` marca
   `setup_completed=true` automáticamente si la empresa ya tiene
   `company_employees_count >= 1` o `tpv_products >= 1` — y el registro
   (`POST /auth/register`) parece sembrar un empleado y un producto TPV por
   defecto para toda empresa nueva. Esto significa que, en la práctica, casi
   ningún usuario real ve nunca `/onboarding-setup` (se le redirige
   directamente a `/dashboard`), lo cual incluye los 3 campos nuevos de esta
   tarea. **Esto es un comportamiento preexistente, no introducido por este
   cambio** — se reporta como hallazgo para que el usuario decida si merece
   una tarea de auditor-priorizador aparte (p. ej., separar "hay datos
   operativos" de "el usuario completó el asistente de facturación").
2. **`alembic upgrade head` desde una BD SQLite completamente vacía falla en
   la migración `0003`** (tabla `document_approvals` no existe aún en ese
   punto de la cadena). Es un problema preexistente de la cadena de
   migraciones antigua, no de la migración `0043` añadida aquí (que sí se
   verificó de forma aislada, ver sección 3). No se ha tocado ninguna
   migración anterior.
3. **`app/core/zeus_agents.py:369`** contiene un campo `"encryption_status":
   "activo"` que es una cadena fija sin cifrado real detrás — no forma parte
   del alcance de esta tarea (no toca IBAN ni facturación), se reporta como
   posible hallazgo de "no simulación" para otra tarea del loop de auditoría.
4. **No se pudo verificar el comportamio exacto en Railway/Postgres en
   producción** (credenciales de Railway no disponibles en este entorno) —
   la migración y el parche idempotente (`_migrate_company_billing_fields`)
   están escritos para ser compatibles con Postgres (`IF NOT EXISTS`), pero
   solo se ha probado contra SQLite local.
5. El `FIELD_ENCRYPTION_KEY` de producción **no existe todavía como variable
   de entorno real en Railway** (no se ha verificado ni se ha inventado). Es
   responsabilidad del despliegue configurarla antes de que haya IBANs reales
   en producción; mientras tanto, el fallback de desarrollo emite un
   `WARNING` explícito en el log de arranque si se ejecuta con
   `ENVIRONMENT=production` sin esa variable.

## 5. Commits

Rama `feature/onboarding-facturacion`, commit(s) atómico(s) — ver `git log`.
Ningún cambio en `main`, ningún `push` a remoto.

---

## Revisión independiente — Vuelta 1

**Veredicto: ❌ DEVUELTO.**

Confirmó de forma independiente y con datos 100% propios (CIF/IBAN construidos con los algoritmos reales, no reutilizados) todo lo esencial: validadores reales (NIF mod-23, CIF, IBAN mod-97, probados contra valores de dominio público), cifrado Fernet real (AES-128-CBC+HMAC, roundtrip correcto, ciphertexts distintos para el mismo IBAN entre tenants), aislamiento multi-tenant, migración con un único head y downgrade simétrico, 0 apariciones del IBAN en claro en logs, suite de tests idéntica al baseline. Los 3 hallazgos declarados confirmados reales, incluido que `zeus_agents.py:369` tiene efectivamente un `encryption_status: "activo"` falso en un handler THALOS.SHIELD simulado.

**Motivo del rechazo:** `crypto.py::_resolve_key()` no falla en cerrado. Si `FIELD_ENCRYPTION_KEY` no está configurada en producción (plausible, es una variable nueva), el sistema registra un `WARNING` y sigue cifrando/descifrando con una clave derivada de `SECRET_KEY` — y `SECRET_KEY` tiene a su vez un valor por defecto hardcodeado en `config.py:324` que tampoco bloquea el arranque, solo advierte. Verificado ejecutando el código real con ambas variables ausentes en un entorno simulado `ENVIRONMENT=production`: el cifrado se produce igual, sin error.

**Por qué es grave:** si `SECRET_KEY` quedara en su valor por defecto (el propio código lo tolera), cualquiera con acceso al código fuente podría derivar la misma clave y descifrar todos los IBANes almacenados, sin necesidad de acceder a la BD ni a ninguna variable de entorno real. Es la misma clase de fallo que ya causó el incidente de seguridad de esta sesión (`44a464a`/`9004b8a`) — mezclar la clave de firma JWT como respaldo silencioso para cifrado de datos financieros en reposo.

**Qué falta para aprobar:** `_resolve_key()` debe lanzar una excepción clara (fallo duro, no `WARNING`) cuando `FIELD_ENCRYPTION_KEY` no esté configurada en producción — como mínimo, la combinación "`FIELD_ENCRYPTION_KEY` ausente + `SECRET_KEY` en su valor por defecto" debe impedir guardar/leer el IBAN, nunca operar silenciosamente. El resto de la implementación (validadores, migración, endpoints, aislamiento, logging) verificado como correcto, puede mantenerse tal cual.
