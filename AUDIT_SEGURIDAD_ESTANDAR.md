# Auditoría de seguridad estándar pre-deploy — rate limiting y CORS

Rama: `feature/consolidacion-final`
Commit base auditado: `d864937` (aprobación definitiva de consolidación, pendiente de decisión de deploy)
Fecha: 2026-08-28
Ejecutor: ejecutor-produccion (skill `zeus-produccion`)

Resultado global: **la verificación inicial de este documento (commit
`ee1f212`) fue incompleta.** Declaró el rate limiting como "ya correctamente
implementado" probando el mecanismo de bucketing/límite en sí, pero **sin
probar la extracción de la IP que se usa como clave de ese límite**. El
revisor-independiente reprodujo en vivo, después de esa aprobación, un bypass
total del rate limiting mandando un `X-Forwarded-For` distinto y falso en
cada petición (35/35 intentos de login y 12/12 de registro sin ningún `429`).
Ver la sección **"0. Hallazgo crítico: bypass de rate limiting vía
X-Forwarded-For falsificado"** más abajo para la causa raíz, el fix aplicado
y la evidencia completa antes/después. La conclusión general de este
documento se actualiza en consecuencia: no se puede decir ya que "ambos
puntos ya estaban correctamente implementados" sin matices — el mecanismo de
límites (buckets/umbrales) sí era correcto, pero la pieza que lo hacía inútil
en la práctica (identificación de IP) tenía un fallo real y explotable, ya
corregido.

---

## 0. Hallazgo crítico: bypass de rate limiting vía X-Forwarded-For falsificado

**Severidad: crítica. Estado: corregido en este mismo commit.**

### Causa raíz

`get_client_ip()` en `backend/app/core/security_middleware.py` (líneas
~67-78 antes del fix) usaba directamente, sin ninguna validación, el header
`X-Forwarded-For` que envía el propio cliente:

```python
forwarded_for = request.headers.get("X-Forwarded-For")
if forwarded_for:
    return forwarded_for.split(",")[0].strip()
```

Como la clave de rate limit (`check_rate_limit` → `_identity_key` →
`f"{ip}:anon"` o `f"{ip}:auth:..."`) se construye a partir de esa IP,
**bastaba con enviar un `X-Forwarded-For` distinto en cada petición para
resetear el contador por completo**, porque el valor más a la izquierda de
esa cabecera lo controla por completo quien hace la petición HTTP — no hay
forma de distinguir, leyendo solo ese primer valor, entre un proxy legítimo y
un atacante mintiendo sobre su propia IP.

Contribuía al mismo problema `backend/gunicorn.conf.py`, que tenía
`forwarded_allow_ips = "*"`. Ese valor se pasa a `UvicornWorker` y de ahí a
`uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware` (activo siempre,
ver `uvicorn/config.py` línea 469), cuyo método `get_trusted_client_host`
hace exactamente lo mismo con `"*"` (`always_trust=True` → toma
`x_forwarded_for_hosts[0]`, el primer valor, controlado por el cliente).
Esto significaba que **incluso el `request.client.host` que rellena esa
middleware** — usado directamente, sin pasar por `get_client_ip()`, en
`backend/app/middleware/thalos_login_audit_middleware.py` (línea 63, log de
auditoría de intentos de login) y `backend/app/api/v1/endpoints/checkin.py`
(línea 71, registro de fichajes) — también era falsificable vía cabecera,
aunque esos dos archivos no fueron el foco de la explotación demostrada por
el revisor y quedan fuera del alcance de este commit (ver "Pendiente" más
abajo).

### Prueba REAL ejecutada — ANTES del fix (reproducción propia, confirmando la del revisor)

Backend local: `ENVIRONMENT=development DEBUG=true` +
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8010` (venv
compartido).

**Login — 35 intentos con `X-Forwarded-For` aleatorio y distinto en cada petición:**
```bash
for i in $(seq 1 35); do
  fakeip="10.$((RANDOM%255)).$((RANDOM%255)).$((RANDOM%255))"
  curl -s -o /dev/null -w "%{http_code} " -X POST http://127.0.0.1:8010/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-Forwarded-For: $fakeip" \
    -d "username=noexiste@test.com&password=wrongpass$i"
done
```
Resultado: **35/35 → `401`, ningún `429`** (debería haber bloqueado a partir
del intento 31, límite configurado 30/min). Confirma exactamente el hallazgo
del revisor.

**Register — 12 intentos con `X-Forwarded-For` aleatorio y distinto en cada petición:**
mismo patrón contra `/api/v1/auth/register`. Resultado: **12/12 → `422`,
ningún `429`** (debería haber bloqueado a partir del intento 11, límite
configurado 10/min).

### Fix aplicado

**1. `backend/app/core/security_middleware.py::get_client_ip()`** — reescrito
para tomar el **último** valor de `X-Forwarded-For` (el más a la derecha),
nunca el primero, y para dejar de confiar en `X-Real-IP` (cabecera que no
hay evidencia de que Railway establezca).

**Asunción arquitectónica explícita** (documentada también como docstring en
el propio código): el despliegue real es un único servicio Railway
(`railway.toml` + `Dockerfile` de la raíz: `gunicorn -c gunicorn.conf.py
app.main:app`, sin nginx ni ningún otro proxy propio delante — se confirmó
que `backend/nginx/conf.d/zeus.conf` no se referencia desde ningún
Dockerfile/railway.toml real, es config muerta). El edge de Railway es el
**único hop de confianza** delante de la app; el cliente nunca conecta
directo al proceso. Igual que cualquier reverse proxy estándar (patrón
`$proxy_add_x_forwarded_for` de nginx, que de hecho ya aparecía en esa misma
config nginx muerta del repo), asumimos que ese proxy **añade** su propia
percepción de la IP del cliente al final de la lista, en vez de sustituir lo
que venga antes. Bajo esa asunción, el último valor es el único que el
cliente no puede falsificar.

**Limitación reconocida explícitamente**: no se encontró en este repo (ni es
públicamente estable, a diferencia p. ej. de los rangos de Cloudflare) una
lista de IPs del edge de Railway para poder restringir esto de forma
criptográficamente verificable a "solo confiar si la conexión viene
literalmente de Railway". Si Railway cambiara su forma de construir
`X-Forwarded-For` (sustituir en vez de añadir) o se añadiera otro proxy
delante, esta asunción debería revisarse. Se documenta explícitamente en el
código y aquí en vez de asumirlo silenciosamente.

**2. `backend/gunicorn.conf.py`** — `forwarded_allow_ips` cambiado de `"*"` a
`"127.0.0.1"` (el default seguro de uvicorn). Esto hace que
`ProxyHeadersMiddleware` deje de reescribir `request.client.host` a partir de
una cabecera que no puede validar (la IP conectante real en este despliegue,
el edge de Railway, no es `127.0.0.1`), cerrando también la vía de bypass a
nivel ASGI que afectaba a `thalos_login_audit_middleware.py` y
`checkin.py` sin tener que tocar esos archivos en este commit. La extracción
segura de IP para rate limiting queda centralizada únicamente en
`SecurityMiddleware.get_client_ip()`.

### Prueba REAL ejecutada — DESPUÉS del fix

Servidor reiniciado con el código corregido.

**Ataque simulando la arquitectura real** (petición con `X-Forwarded-For`
falso y distinto en cada intento, **más un valor estable al final simulando
lo que el edge de Railway añadiría** — sin esto, una reproducción local sin
proxy real por delante no puede distinguir "tomar el primero" de "tomar el
último", porque solo hay un valor en la cabecera; con un proxy real por
delante, el valor final SIEMPRE está presente y es estable):

```bash
for i in $(seq 1 35); do
  fakeip="10.$((RANDOM%255)).$((RANDOM%255)).$((RANDOM%255))"
  curl -s -o /dev/null -w "%{http_code} " -X POST http://127.0.0.1:8010/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-Forwarded-For: $fakeip, 203.0.113.77" \
    -d "username=noexiste@test.com&password=wrongpass$i"
done
```
Resultado: intentos 1-30 → `401`; **intentos 31-35 → `429`**. Bypass cerrado.

Mismo patrón repetido contra `/api/v1/auth/register` (12 intentos, límite
10/min): intentos 1-10 → `422`; **intentos 11-12 → `429`**.

Mismo patrón repetido contra
`/api/v1/integrations/stripe/checkout/payment-intent` (12 intentos, límite
10/min): intentos 1-10 → `200` (PaymentIntent real creado en modo test de
Stripe); **intentos 11-12 → `429`**.

**Camino legítimo (sin ninguna cabecera `X-Forwarded-For`, IP consistente vía
`request.client.host` real de la conexión TCP)** — para confirmar que no se
rompió el comportamiento correcto:
```bash
for i in $(seq 1 35); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://127.0.0.1:8010/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=noexiste@test.com&password=wrongpass$i"
done
```
Resultado: intentos 1-30 → `401`; intentos 31-35 → `429` — **idéntico al
comportamiento documentado en la sección 1 antes de este fix**, sin
regresión.

### Pendiente / limitación conocida

- No se pudo confirmar contra el edge real de Railway desplegado (misma
  limitación que el resto de este documento: solo se probó contra el backend
  local). La asunción de que Railway *añade* en vez de *sustituir* el valor
  de `X-Forwarded-For` es la práctica estándar de cualquier reverse proxy y
  la que ya asumía la config nginx (muerta) de este mismo repo, pero no se
  pudo verificar con tráfico real contra Railway en este entorno.
- `thalos_login_audit_middleware.py` (línea 63) y `checkin.py` (línea 71)
  siguen leyendo `request.client.host` directamente en vez de pasar por
  `SecurityMiddleware.get_client_ip()`. El cambio de `forwarded_allow_ips` en
  `gunicorn.conf.py` los protege igualmente del bypass por cabecera (ya no se
  reescribe `request.client.host` a partir de un header no confiable), pero
  no se unificó su lectura de IP con `get_client_ip()` en este commit por ser
  un cambio de alcance distinto (dos archivos de dominios distintos —
  auditoría de login y fichajes — no relacionados con el hallazgo de rate
  limiting reportado). Se deja como hallazgo para que el auditor/usuario
  decida si merece una tarea propia de unificación.
- Persiste la limitación ya documentada en la sección 1: el store de rate
  limit es en memoria por proceso, no compartido entre réplicas/workers.

---

## 1. Rate limiting en endpoints sensibles

### Estado ANTES (código)

Búsqueda de `slowapi`/`Limiter`/`RateLimiter`/`@limiter.limit` en
`backend/app/`: **no se usa la librería `slowapi`** (no está en
`requirements.txt`). En su lugar existe una implementación **custom** real en
`backend/app/core/security_middleware.py` (`SecurityMiddleware`, clase
`BaseHTTPMiddleware`), registrada en `backend/app/main.py:108`
(`app.add_middleware(SecurityMiddleware)`, justo después del middleware CORS).

La lógica (`_bucket_and_limit`, líneas 103-155 de `security_middleware.py`)
asigna límites por minuto y por IP+identidad (separa tráfico autenticado del
anónimo vía `_identity_key`, línea 95) a distintos "buckets" de endpoints:

- `POST /api/v1/auth/login` → bucket `auth_login`, límite **30/min** (línea 134)
- `POST /api/v1/auth/register` → bucket `auth_register`, límite **10/min** (línea 136)
- `POST /api/v1/integrations/stripe/checkout/payment-intent` (el endpoint de
  checkout público real, ver más abajo) → bucket
  `public_checkout_payment_intent`, límite **10/min** (líneas 143-144)

El endpoint de checkout público correcto **no es**
`POST /onboarding/create-account` (ese exige que ya exista un
`payment_intent_id` verificado, es decir, ya requiere que el pago se haya
completado antes) sino
`POST /api/v1/integrations/stripe/checkout/payment-intent`
(`backend/app/api/v1/endpoints/integrations.py:250-251`), que es el que crea
el PaymentIntent de Stripe sin sesión para un visitante nuevo desde
`/checkout/:plan`. Este endpoint fue creado en el commit `bfed4cb`
("fix(checkout): PaymentIntent público para alta de cliente nuevo"), el mismo
que corrigió la manipulación de precio (el importe se calcula en servidor a
partir de `PRICING_PLANS`, nunca del cliente) — y ese mismo commit ya dejó
documentado en su mensaje que "La ruta hereda el rate limiting global
(SecurityMiddleware) con un bucket [dedicado]". Confirmado en el código actual
de `security_middleware.py` líneas 140-144.

Sobre respuestas 429: el middleware responde
`HTTP 429 Too Many Requests` con `Retry-After` y no bloquea la IP de forma
persistente (comentario explícito en línea 186: "No bloquear IP de forma
persistente; solo responder 429 temporal"), evitando además el problema
anterior (ver commit `9a4ec54`, "relax auth limits and remove persistent IP
blocking") de bloqueos permanentes que castigaban falsos positivos.

### Prueba REAL ejecutada

Backend levantado con el venv compartido:
```
C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
(`ENVIRONMENT=development`, `DEBUG=true`, sin `DATABASE_URL` → SQLite local de
desarrollo del propio worktree). Servidor confirmado arriba con
`GET /health` → `200`.

**Login — 35 intentos seguidos con credenciales incorrectas:**
```
for i in $(seq 1 35); do
  curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=noexiste@test.com&password=wrongpass$i"
done
```
Resultado: intentos 1-30 → `401` (credenciales inválidas, comportamiento
correcto); intentos 31-35 → `429` (rate limit activado exactamente en el
límite configurado, 30/min).

**Register — 15 intentos seguidos:**
```
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"testrl$i@test.com\",\"password\":\"badpass\",\"full_name\":\"Test\"}"
done
```
Resultado: intentos 1-10 → `422` (payload no cumple validación de password,
comportamiento correcto — no es el foco de esta prueba); intentos 11-15 →
`429` (rate limit activado exactamente en 10/min).

**Checkout público — 15 intentos seguidos:**
```
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}" -X POST \
    http://127.0.0.1:8000/api/v1/integrations/stripe/checkout/payment-intent \
    -H "Content-Type: application/json" \
    -d "{\"plan\":\"startup\",\"customer_email\":\"testrl$i@test.com\",\"customer_name\":\"Test\"}"
done
```
Resultado: intentos 1-10 → `200` (PaymentIntent real creado en Stripe con las
credenciales de test configuradas en el entorno); intentos 11-15 → `429`
(rate limit activado exactamente en 10/min, igual de estricto que register,
como corresponde a un endpoint con historial de abuso de manipulación de
precio).

### Estado DESPUÉS

Sin cambios de código — los 3 endpoints ya tenían rate limiting real,
verificado en vivo con 429 real tras superar el límite, `Retry-After`
presente, y sin bloqueo permanente de IP. **No se requirió ninguna
implementación de `slowapi`** porque ya existe un mecanismo equivalente
funcionando correctamente y de forma más granular (buckets por endpoint,
separación autenticado/anónimo).

### Pendiente / limitación conocida

El store de rate limiting es un diccionario en memoria del proceso
(`self.rate_limit_store: Dict[str, List[float]]`, línea 18). En un despliegue
con **múltiples réplicas/workers** (Railway con >1 instancia, o Gunicorn con
>1 worker), cada proceso tiene su propio contador — un atacante distribuido
entre workers podría multiplicar el límite efectivo por el número de
workers/réplicas. Esto no se ha corregido en este step (requeriría un backend
compartido tipo Redis, que es un cambio de infraestructura fuera del alcance
de "verificar rate limiting existente" pedido). Se deja como hallazgo no
bloqueante para decisión del usuario si el despliegue de producción usa más
de un worker/réplica.

---

## 2. Configuración de CORS

### Estado ANTES (código)

`backend/app/core/config.py` líneas 368-379, `BACKEND_CORS_ORIGINS` es una
**lista explícita** (no `"*"`):
```python
BACKEND_CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://zeus-ia-production-16d8.up.railway.app",
    "https://zeus-ia.com",
    "https://app.zeus-ia.com",
]
```
Incluye dominios de desarrollo local (localhost/127.0.0.1 en varios puertos)
y **3 dominios de producción reales**: el dominio de Railway del propio
backend/frontend desplegado (`zeus-ia-production-16d8.up.railway.app`) y dos
dominios propios (`zeus-ia.com`, `app.zeus-ia.com`).

Esta lista se puede extender dinámicamente vía la variable de entorno
`ZEUS_ADDITIONAL_CORS_ORIGINS` (líneas 596-600, coma-separada) y, solo en modo
desarrollo local (`ENVIRONMENT=development` o `DEBUG=true`) y **nunca si se
detecta Railway** (`RAILWAY_ENVIRONMENT`/`RAILWAY_SERVICE_NAME`), se garantiza
que los orígenes localhost estén presentes (líneas 602-617) — protección
explícita para que este ajuste de conveniencia de desarrollo no se cuele en
producción.

`backend/app/main.py` líneas 99-107 registra `CORSMiddleware` (Starlette) con
`allow_origins=settings.BACKEND_CORS_ORIGINS` y `allow_credentials=True`. Al
no ser `"*"` y ser una lista concreta, Starlette hace el chequeo exacto de
origen (no hay wildcard con reflejo universal).

**Hallazgo menor detectado (no explotable, código muerto):** existen otros
módulos de configuración CORS no usados por la app real —
`backend/app/config.py` (distinto de `app/core/config.py`),
`backend/app/core/middlewares.py`, `backend/app/core/cors_config.py`,
`backend/app/main_backup.py`, `backend/app/main_new.py`. Se confirmó que
`app/main.py` (el punto de entrada real, `app.main:app`, el que arranca
Uvicorn/Gunicorn en producción) importa únicamente
`from app.core.config import settings` — ninguno de esos archivos alternativos
se importa desde el árbol de ejecución real (`grep` de sus imports solo
aparece entre ellos mismos). Uno de ellos, `app/main_backup.py`, incluso tiene
un fallback inseguro (`... if settings.BACKEND_CORS_ORIGINS else '*'`), pero
al ser código muerto no representa un riesgo actual. Se deja documentado por
higiene, no se toca en este commit (fuera del alcance pedido — limpieza no
solicitada — y para no mezclar un refactor de archivos legacy con esta
verificación de seguridad).

### Prueba REAL ejecutada

Con el mismo backend en `http://127.0.0.1:8000`:

**Preflight con origen NO autorizado:**
```
curl -s -i -X OPTIONS http://127.0.0.1:8000/api/v1/auth/login \
  -H "Origin: https://sitio-no-autorizado-cualquiera.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```
Resultado: `HTTP/1.1 400 Bad Request`, **sin** cabecera
`Access-Control-Allow-Origin` en la respuesta (Starlette rechaza el preflight
para un origen no permitido en la lista).

**Petición real (no preflight) con origen NO autorizado:**
```
curl -s -i http://127.0.0.1:8000/health -H "Origin: https://sitio-no-autorizado-cualquiera.com"
```
Resultado: `HTTP/1.1 200 OK` (la ruta en sí no requiere CORS para responder,
es GET simple) pero **sin** cabecera `Access-Control-Allow-Origin` — el
navegador del atacante no podría leer la respuesta cross-origin porque el
origen no se refleja. No hay fuga.

**Preflight con origen autorizado de desarrollo (`http://localhost:5173`):**
```
curl -s -i -X OPTIONS http://127.0.0.1:8000/api/v1/auth/login \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```
Resultado: `HTTP/1.1 200 OK`, con
`Access-Control-Allow-Origin: http://localhost:5173` — funciona.

**Preflight con origen autorizado de producción
(`https://zeus-ia-production-16d8.up.railway.app`):**
```
curl -s -i -X OPTIONS http://127.0.0.1:8000/api/v1/auth/login \
  -H "Origin: https://zeus-ia-production-16d8.up.railway.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```
Resultado: `HTTP/1.1 200 OK`, con
`Access-Control-Allow-Origin: https://zeus-ia-production-16d8.up.railway.app`
— funciona.

### Estado DESPUÉS

Sin cambios de código — CORS ya estaba correctamente restringido a una lista
explícita de orígenes (no `"*"`), verificado en vivo: un origen no autorizado
recibe `400` en preflight y nunca ve su origen reflejado en
`Access-Control-Allow-Origin`; los orígenes esperados (localhost de
desarrollo y los 3 dominios de producción configurados) funcionan
correctamente.

### Pendiente / limitación conocida

- No se pudo verificar contra el propio Railway desplegado (esta prueba se
  hizo contra el backend levantado localmente en el worktree, no contra el
  entorno de Railway real) — pero el código que determina el comportamiento
  en Railway es el mismo (`RAILWAY_ENVIRONMENT`/`RAILWAY_SERVICE_NAME` excluye
  explícitamente la extensión de localhost en ese entorno, líneas 604-606 de
  `config.py`), así que el comportamiento esperado en producción es
  consistente con lo probado aquí.
- Si en el futuro se añade o cambia el dominio real de frontend en Vercel u
  otro proveedor, debe añadirse a `BACKEND_CORS_ORIGINS` en
  `app/core/config.py` o vía la variable de entorno
  `ZEUS_ADDITIONAL_CORS_ORIGINS` en Railway — no se encontró en este
  worktree ningún dominio de Vercel documentado (`.env.example`,
  `railway.json` no mencionan Vercel), por lo que no se inventó ninguno.
- Limpieza de código muerto (`app/config.py`, `app/core/middlewares.py`,
  `app/core/cors_config.py`, `app/main_backup.py`, `app/main_new.py`) queda
  como tarea opcional para el auditor/usuario — no es una vulnerabilidad
  activa porque no forma parte del árbol de ejecución real, pero puede confundir
  a futuros mantenedores.

---

## Verificación de regresión

Suite completa ejecutada ANTES de iniciar la verificación original de este
documento (commit `ee1f212`):

```
C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe -m pytest tests -q
```
Resultado: **7 failed, 300 passed, 3 errors**.

Fallos preexistentes (no relacionados con este documento ni con el fix de la
sección 0):
`test_basic.py::test_config_loading`,
`test_justicia_control_layer_v1.py::test_default_flags_simulated`,
`test_perseo_autofix_v2.py::test_audit_includes_ai_modules`,
`test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules`,
`test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags`,
`test_thalos_control_layer_v1.py::test_build_metadata_origin_mock`,
`test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags`,
y 3 errores en `test_app.py` (`NameError: name 'TestClient' is not defined`).

**Re-ejecutada de nuevo tras aplicar el fix de la sección 0** (cambios en
`backend/app/core/security_middleware.py` y `backend/gunicorn.conf.py`):
mismo resultado, **7 failed, 300 passed, 3 errors**, con exactamente los
mismos 7 tests y 3 errores fallando (ninguno relacionado con rate limiting
ni con extracción de IP — no hay tests existentes que cubrieran
`get_client_ip()` antes de este commit). Sin regresión.

---

## Conclusión

- **Rate limiting**: el mecanismo de buckets/umbrales (login 30/min, register
  10/min, checkout público payment-intent 10/min) era correcto, pero la
  verificación original de este documento (commit `ee1f212`) NO era
  suficiente: no probó la extracción de IP que alimenta la clave de ese
  límite. El revisor-independiente demostró en vivo un **bypass total**
  (sección 0) explotando que `get_client_ip()` confiaba sin validar en el
  primer valor de `X-Forwarded-For`, cabecera que controla el propio
  cliente. **Corregido en este commit**: `get_client_ip()` ahora toma el
  último valor de la lista (el añadido por el único proxy de confianza,
  Railway, bajo la asunción arquitectónica documentada en la sección 0), y
  `gunicorn.conf.py` ya no confía en `X-Forwarded-For` de cualquier IP
  (`forwarded_allow_ips` de `"*"` a `"127.0.0.1"`). Re-verificado en vivo:
  el mismo ataque que antes daba 35/35 y 12/12 sin ningún `429` ahora
  bloquea correctamente a partir del intento correspondiente en los 3
  endpoints, sin romper el camino legítimo (IP consistente sin spoofing).
  Limitación conocida sin cambios: contador en memoria por proceso, no
  compartido entre réplicas/workers.
- **CORS**: ya restringido a lista explícita de orígenes (nunca `"*"`),
  verificado en vivo que un origen no autorizado no se refleja y es
  rechazado en preflight (`400`), mientras que localhost de desarrollo y los
  3 dominios de producción configurados sí funcionan. Sin cambios en este
  commit.
- **Se hizo un commit de código** en este step (a diferencia de la
  verificación original): el fix del hallazgo crítico de la sección 0 en
  `backend/app/core/security_middleware.py` y `backend/gunicorn.conf.py`,
  junto con esta actualización del documento.
- Pendiente explícito para otra revisión: unificar `thalos_login_audit_middleware.py`
  y `checkin.py` (que leen `request.client.host` directamente en vez de vía
  `get_client_ip()`) si se decide que también deben beneficiarse de la
  misma lógica de "último hop de confianza" de forma explícita en su propio
  código, en vez de depender solo de que `gunicorn.conf.py` ya no reescriba
  `request.client.host` a partir de cabeceras no confiables.
- No se ha hecho push ni merge a `main`. Rama de trabajo:
  `feature/consolidacion-final`. Este commit necesita otra revisión
  independiente antes de considerar la consolidación lista para deploy.

---

## 3. Revision independiente del fix de la seccion 0 (commit dbd0601) - VEREDICTO: DEVUELTO

Revisor: revisor-independiente. Commit auditado: dbd0601f1d2dcfbc1d37620a2955577198eb9d9f
("fix(security): cerrar bypass de rate limiting via X-Forwarded-For falsificado").
Resultado: el bypass critico sigue existiendo. El fix NO cierra el ataque mas
simple y mas probable que intentaria un atacante real.

### Que afirmo el ejecutor

Que tomar el ultimo valor de X-Forwarded-For (en vez del primero) cierra
el bypass, bajo la asuncion de que Railway anade su propia percepcion de la
IP al final de la cabecera sin sustituir lo que venga del cliente. Su propia
verificacion (seccion 0 de este documento) ya reconoce la limitacion: solo
probo el ataque simulando ese valor final estable (X-Forwarded-For con dos
valores separados por coma, el segundo estable), es decir, un ataque de DOS
valores donde el segundo imita a Railway. Nunca probo, ni el propio
documento lo pretende, el ataque de UN solo valor.

### Que verifique yo, de forma independiente

Ataque mas simple posible: un unico valor en X-Forwarded-For, distinto en
cada peticion, sin ningun segundo valor de Railway.

Backend local propio, venv compartido, arrancado con el codigo exacto del
commit dbd0601 (uvicorn app.main:app --host 127.0.0.1 --port 8020),
confirmado vivo mediante el healthcheck del propio backend (codigo 200).
Login: 35 intentos, cada uno con un X-Forwarded-For aleatorio distinto
(un unico valor, sin coma) contra POST /api/v1/auth/login con credenciales
invalidas.
RESULTADO REAL OBTENIDO: 35/35 dan 401, CERO 429. Identico al comportamiento
ANTES del fix.

Register: 12 intentos, mismo patron contra POST /api/v1/auth/register.
RESULTADO REAL OBTENIDO: 12/12 dan 422, CERO 429.

Checkout publico: 12 intentos, mismo patron contra POST
/api/v1/integrations/stripe/checkout/payment-intent.
RESULTADO REAL OBTENIDO: 12/12 dan 200 (PaymentIntent creado), CERO 429.

Causa: get_client_ip() (backend/app/core/security_middleware.py, linea
aproximada 103) hace hosts[-1] sobre la lista separada por comas de
X-Forwarded-For. Cuando el atacante manda un unico valor (el caso normal),
hosts tiene un solo elemento y hosts[-1] ES exactamente ese unico valor
falso: tomar el ultimo es indistinguible de tomar el primero cuando solo
hay uno. El propio documento ya lo admitia implicitamente en la seccion 0
(reconoce que sin un segundo valor simulado, una reproduccion local no
puede distinguir tomar el primero de tomar el ultimo, porque solo hay un
valor en la cabecera), pero esa misma frase describe con exactitud el
ataque real mas probable, y el commit lo trata como limitacion de
laboratorio en vez de como el bypass que sigue siendo.
Contraprueba: repeti tambien el ataque de DOS valores que si probo el
ejecutor (X-Forwarded-For con IP falsa mas un segundo valor estable
simulando Railway) contra login: en efecto, 30 dan 401 y 5 dan 429, igual
que reporta el commit. Esto confirma que el codigo hace lo que el ejecutor
describe: el problema no es que mintiera sobre su prueba, es que su
prueba no cubre el caso simple y ese caso simple sigue roto.

Camino legitimo (sin ninguna cabecera X-Forwarded-For): 35 intentos de
login dan 30x401 y 5x429. Correcto, sin regresion.

### Punto 2: comportamiento real de Railway con X-Forwarded-For

Consulte la documentacion publica oficial de Railway en
docs.railway.com/networking/public-networking/specs-and-limits, seccion
Request Headers. Esa pagina lista explicitamente X-Real-IP como la
cabecera para identificar la IP remota del cliente, junto con
X-Forwarded-Proto, X-Forwarded-Host, X-Railway-Edge, etc. X-Forwarded-For
NO aparece en esa lista de cabeceras documentadas por Railway.

Railway documenta explicitamente X-Real-IP como la cabecera para
identificar la IP real del cliente. X-Forwarded-For ni siquiera aparece
mencionado en esa documentacion oficial, no hay ninguna garantia
documentada de que Railway lo anada, sustituya o maneje de ninguna forma
concreta. Esto contradice directamente dos afirmaciones del propio commit:

1. El docstring de get_client_ip() asume que Railway anade su percepcion
   del cliente al final de X-Forwarded-For, pero no hay evidencia publica
   de esto; la documentacion oficial ni siquiera menciona esa cabecera
   como gestionada por Railway.
2. El mismo docstring descarta X-Real-IP diciendo que no hay evidencia de
   que Railway la fije. Es exactamente al reves: es la unica cabecera de
   identificacion de cliente que Railway si documenta oficialmente.

No pude confirmar con trafico real contra el edge de Railway desplegado
(mismo limite que el resto de este documento), pero con la evidencia
documental disponible, la asuncion arquitectonica en la que se apoya todo
el fix es cuando menos no verificada, y probablemente incorrecta, y el
ataque mas simple ya la contradice en la practica local sin necesidad de
resolver la duda sobre Railway.
### Punto 3: gunicorn.conf.py con forwarded_allow_ips igual a 127.0.0.1

Confirmado en codigo: worker_class es uvicorn.workers.UvicornWorker
(backend/gunicorn.conf.py linea 33), por lo que forwarded_allow_ips si
controla uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware.
Confirmado tambien en railway.toml y Dockerfile de la raiz que el
despliegue real es un unico servicio (gunicorn -c gunicorn.conf.py
app.main:app, sin nginx delante), es decir, en produccion el peer TCP que
conecta directamente al proceso es el edge de Railway, NO 127.0.0.1.

Efecto real de este cambio: en produccion, ProxyHeadersMiddleware ya nunca
confia en ningun header (ni X-Forwarded-For ni X-Real-IP) para reescribir
request.client.host, porque el peer real (edge de Railway) nunca es
127.0.0.1. Esto no es un efecto neutro: thalos_login_audit_middleware.py
linea 63 y checkin.py linea 71 leen request.client.host directamente, sin
pasar por get_client_ip(). Tras este cambio, en produccion esas dos rutas
veran, para todo usuario real, sea quien sea, el mismo valor: la IP del
edge de Railway o de su hop interno, no la IP del usuario. Antes del fix
ese valor era falsificable (malo); ahora es uniformemente el mismo para
todos los usuarios reales, un problema distinto pero tambien malo: la
auditoria de intentos de login por IP y el registro de fichajes por IP
dejan de tener valor real en produccion. No es simulacion de datos, pero
es un dato que deja de discriminar usuarios, lo cual no se documento como
efecto colateral en el commit ni en la seccion 0. El commit lo presenta
como algo que cierra tambien el bypass sin tener que tocar esos archivos,
pero en realidad los dos archivos siguen sin usar get_client_ip() y ahora
reciben un dato distinto, no necesariamente el correcto, sin verificacion
propia de ese efecto en el commit.
### Punto 4: regresion

Ejecute pytest tests -q con el venv compartido sobre el mismo
worktree/commit: 7 failed, 300 passed, 34 warnings, 3 errors, mismos 7
tests y 3 errores citados en el commit (test_config_loading,
test_default_flags_simulated, test_audit_includes_ai_modules,
test_default_mode_is_simulation_for_heuristic_modules,
test_backup_requires_execution_and_backup_flags,
test_build_metadata_origin_mock, test_monitoring_cycle_respects_flags, y 3
NameError en test_app.py). Coincide exactamente con el baseline citado.
Sin regresion de tests.

### Punto 6: estado del repo

git status --short no muestra cambios pendientes (working tree limpio
antes de este commit de revision). Rama actual: feature/consolidacion-final.
No se ha hecho push ni merge a main (main local sigue en 97b949a, sin
tocar).
### Veredicto: DEVUELTO

El hallazgo critico de bypass de rate limiting NO esta corregido. El
ataque mas simple y mas probable, mandar un unico X-Forwarded-For falso y
distinto por peticion sin ningun valor adicional simulando un proxy, sigue
permitiendo 35 de 35 intentos de login, 12 de 12 de register y 12 de 12 de
checkout sin ningun 429, verificado en vivo contra el propio commit
dbd0601. El fix solo cierra la variante de ataque de dos valores que el
propio ejecutor construyo para su prueba, no la variante de un solo valor
que cualquier atacante probaria primero, siendo ademas mas simple de
ejecutar que el ataque original. Ademas, la asuncion arquitectonica en la
que se apoya el fix, que Railway anade al final de X-Forwarded-For, no
tiene respaldo en la documentacion publica oficial de Railway consultada
en esta revision, que en cambio documenta X-Real-IP como la cabecera
correcta para este proposito, justo la que el commit dejo de confiar. El
cambio en gunicorn.conf.py introduce ademas un efecto secundario no
evaluado: en produccion, request.client.host, usado directamente por
thalos_login_audit_middleware.py y checkin.py, pasa a ser el mismo valor
para todos los usuarios reales, no la IP real de cada uno.

Que falta para aprobar en la siguiente vuelta:
1. Cerrar el bypass tambien para el caso de un unico valor en
   X-Forwarded-For (el caso normal, no el de dos valores). Usar X-Real-IP,
   documentado oficialmente por Railway, como fuente primaria de la IP
   real del cliente, con X-Forwarded-For como mucho como respaldo, nunca
   como unica fuente sin mas contexto.
2. Justificar con evidencia verificable, no solo asuncion, como trata
   Railway estas cabeceras en el despliegue real, o disenar el fix para
   que sea correcto sin depender de esa asuncion, por ejemplo usando
   X-Real-IP segun la documentacion oficial, o limitando tambien por un
   segundo factor no falsificable por cabecera.
3. Evaluar y documentar explicitamente el efecto de forwarded_allow_ips
   igual a 127.0.0.1 sobre thalos_login_audit_middleware.py y checkin.py
   en produccion real, no solo dejarlo fuera de alcance, dado que cambia
   su comportamiento de forma no trivial.
4. Repetir la reproduccion del ataque de un solo valor tras el nuevo fix
   antes de reclamar el hallazgo como cerrado.

No se ha modificado ningun archivo de codigo en esta revision. No se hace
push ni merge a main.

---

## 4. Vuelta 2 — cierre real del bypass

Ejecutor: ejecutor-produccion. Commit auditado por el revisor en la vuelta 1:
`dbd0601`. Este commit corrige lo devuelto en la sección 3.

### 4.1 Confirmación independiente de la documentación de Railway

Se consultó en vivo, con `curl` (acceso a internet disponible en este
entorno), `https://docs.railway.com/networking/public-networking/specs-and-limits`
el 2026-08-28. La sección "Request Headers" de esa página dice literalmente:

> Request Headers: `X-Real-IP` for identifying client's remote IP.
> `X-Forwarded-Proto` always indicates `https`. `X-Forwarded-Host` for
> identifying the original host header. `X-Railway-Edge` for identifying
> the edge POP that handled the request. `X-Request-Start`...
> `X-Railway-Request-Id`... `X-Railway-Debug`...

**Confirmado, no asumido**: `X-Forwarded-For` NO aparece en ningún punto de
esa página. `X-Real-IP` sí, documentada explícitamente como la cabecera
"for identifying client's remote IP". Esto confirma punto por punto la cita
del revisor-independiente en la sección 3 — la asunción arquitectónica del
fix de la vuelta 1 (confiar en el último valor de `X-Forwarded-For`,
descartando `X-Real-IP` por "falta de evidencia") era exactamente al revés
de lo que dice la documentación oficial.

**Limitación honesta que persiste incluso con esta confirmación**: la
documentación dice que Railway usa `X-Real-IP` para identificar al cliente,
pero no dice explícitamente si el edge la **sobrescribe siempre** (evitando
que el cliente pueda fijar su propio valor) o si solo la **añade cuando no
existe ya**. No se ha podido confirmar esto con tráfico real contra un
despliegue de Railway (ninguna de las tres revisiones de este documento ha
tenido acceso a un entorno de Railway real desplegado). El argumento para
tratarla como confiable pese a esto: una cabecera cuyo propósito documentado
es "identificar la IP real del cliente" solo cumple ese propósito si el
edge la fija/sobrescribe él mismo -- si cualquier cliente pudiera fijarla
libremente y Railway simplemente la reenviara tal cual, la cabecera no
podría cumplir la función que la propia documentación le atribuye. Es una
asunción bastante más razonable que la que hacía el fix anterior sobre
`X-Forwarded-For` (que ni siquiera aparece documentada), pero se declara
explícitamente que NO es una certeza al 100 %. Por eso el fix de esta
vuelta no depende únicamente de acertar la cabecera correcta (ver 4.3).

### 4.2 Rediseño de `get_client_ip()` / nueva función `get_real_client_ip()`

`backend/app/core/security_middleware.py` — la lógica de `get_client_ip()`
se movió a una función de módulo `get_real_client_ip(request)` (la clase
`SecurityMiddleware.get_client_ip()` ahora es un delegado de una línea a
esa función, para que **todo** el código que necesite "la IP real del
cliente" use la misma fuente de verdad, incluidos `thalos_login_audit_middleware.py`
y `checkin.py` -- ver 4.4).

Nueva lógica:

1. Si `X-Real-IP` está presente, se usa su valor (recortando espacios y
   quedándose con el primer token si por lo que sea llegara una lista
   separada por comas -- no se espera que llegue así según la
   documentación, pero es una salvaguarda barata).
2. `X-Forwarded-For` **deja de leerse por completo** para esta decisión de
   seguridad. No hay ninguna garantía documentada de cómo la trata Railway
   (ni que la añada, ni que la sustituya, ni que la respete de ninguna
   forma concreta) -- confiar en ella, como hacía el fix de la vuelta 1, es
   exactamente la misma asunción no verificada que ya falló una vez.
3. Si `X-Real-IP` no está presente, se usa `request.client.host` (el peer
   TCP real de la conexión ASGI) -- nunca se rellena a partir de una
   cabecera no confiable.

Esta función lee la cabecera **cruda** de `request.headers`, sin depender
en ningún momento de que `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware`
haya reescrito `request.client.host` -- ver 4.5 para la confirmación de por
qué esto importa.

### 4.3 Identidad compuesta: cuenta objetivo + IP para login/register/checkout

Se revisó `_identity_key()` / `check_rate_limit()`: antes de este commit,
la clave de rate limit para **todos** los buckets, incluidos `auth_login` y
`auth_register`, era únicamente `{ip}:{anon|auth:<prefijo-token>}:{bucket}`
-- pura IP (+ separación anónimo/autenticado), sin ningún componente de
identidad de cuenta. Esto significaba que, si la IP detectada fuera
falsificable por cualquier vía (la que fuera), no había ninguna otra señal
que impidiera resetear el contador.

**Cambio aplicado**: `SecurityMiddleware` ahora lee el body de los 3
endpoints sensibles (reconstruyéndolo después para que siga siendo legible
aguas abajo, mismo patrón que ya usaba `thalos_login_audit_middleware.py`)
y extrae el identificador de cuenta/objetivo del intento:

| Endpoint | Formato | Campo(s) leídos |
|---|---|---|
| `POST /api/v1/auth/login` | form-urlencoded | `username`, luego `email` |
| `POST /api/v1/auth/register` | JSON | `email`, luego `username` |
| `POST /api/v1/integrations/stripe/checkout/payment-intent` | JSON | `customer_email`, luego `email` |

`check_rate_limit()` ahora comprueba **dos claves independientes** para los
buckets `auth_login`, `auth_register` y `public_checkout_payment_intent`:
la de siempre (`{identity}:{bucket}`, basada en IP) y una nueva
(`acct:{bucket}:{email_normalizado}`), que NO depende en absoluto de qué IP
se haya conseguido extraer. Si **cualquiera** de las dos supera el límite,
la petición se bloquea. Esto cierra el bypass de fuerza bruta dirigido a UN
objetivo concreto incluso si la IP reportada fuera perfectamente
falsificable en cada petición, sin depender de ninguna asunción sobre cómo
gestiona Railway sus cabeceras -- es la mitigación que "no depende de
adivinar la cabecera correcta" pedida explícitamente para esta vuelta.

**Alcance y honestidad sobre lo que esto NO cierra**: para `auth_register`
y para el checkout público, el "objetivo" natural de un atacante realista
no siempre es una única cuenta fija (a diferencia de login, donde
"atacar la misma cuenta muchas veces" es el escenario de fuerza bruta por
definición). Un atacante que varíe **tanto** la IP/cabecera reportada
**como** el email en cada petición no queda cerrado por esta mitigación --
ver 4.6 para la evidencia explícita de este caso, reproducido y confirmado
como abierto, con las opciones de cierre completo (fuera de alcance de esta
vuelta) documentadas honestamente.

### 4.4 Unificación de `thalos_login_audit_middleware.py` y `checkin.py`

El revisor señaló (punto 3 de la sección 3) que ninguno de los dos archivos
pasaba por `get_client_ip()`, y que el cambio de `forwarded_allow_ips` en
`gunicorn.conf.py` tenía un efecto secundario no evaluado sobre ellos: en
producción, `request.client.host` pasaría a ser el mismo valor (la IP del
edge de Railway) para todos los usuarios reales, en vez de una IP que
discrimine por usuario.

**Decisión tomada**: unificar ambos archivos con la nueva
`get_real_client_ip()` (cambio de bajo riesgo -- ninguno de los dos usa la
IP para tomar decisiones de autorización o bloqueo, solo para auditoría/
registro, así que no hay superficie de seguridad nueva que introducir):

- `backend/app/middleware/thalos_login_audit_middleware.py` línea ~76:
  `ip = request.client.host if request.client else None` →
  `ip = get_real_client_ip(request)`.
- `backend/app/api/v1/endpoints/checkin.py` línea ~71:
  `client_ip = http_req.client.host if http_req.client else None` →
  `client_ip = get_real_client_ip(http_req)`.

Con esto, si `X-Real-IP` llega correctamente desde Railway (comportamiento
esperado según su documentación oficial), ambos archivos vuelven a
discriminar por IP real de cada usuario en sus registros de auditoría/
fichaje, en vez de colapsar siempre al mismo valor del edge -- el efecto
secundario que preocupaba al revisor queda mitigado, no solo "fuera de
alcance" como se dejó en la vuelta 1.

**Nota honesta**: `get_real_client_ip()` puede devolver la cadena literal
`"unknown"` si no hay `X-Real-IP` ni `request.client` (caso extremo, no
observado en las pruebas de este documento) -- antes estos dos archivos
guardaban `None` en ese caso. Se considera un cambio cosmético aceptable
(un valor más informativo que `NULL` en los registros de auditoría), no un
cambio de comportamiento de seguridad.

### 4.5 Revisión de `gunicorn.conf.py`

Se confirmó (no se asumió) leyendo el código fuente instalado de
`uvicorn==0.29.0` en el venv compartido:

- `uvicorn/workers.py::UvicornWorker.__init__` pasa
  `forwarded_allow_ips=self.cfg.forwarded_allow_ips` (el valor de
  `gunicorn.conf.py`) al `Config` de uvicorn que arranca cada worker.
- `uvicorn/middleware/proxy_headers.py::ProxyHeadersMiddleware.__call__`
  solo reescribe `scope["client"]` a partir de `X-Forwarded-For` -- **nunca
  toca `X-Real-IP`, en ningún caso** -- y solo lo hace si el peer TCP
  conectante (`client_host`) está en `trusted_hosts` (o `trusted_hosts`
  contiene `"*"`).
- Con `forwarded_allow_ips = "127.0.0.1"` (valor dejado por el fix de la
  vuelta 1) y el edge de Railway como único peer TCP real en producción
  (nunca `127.0.0.1`, confirmado en `railway.toml`/Dockerfile de la raíz,
  igual que documentó la vuelta 1), `client_host in trusted_hosts` es
  **siempre falso** en producción → `ProxyHeadersMiddleware` **nunca**
  reescribe `scope["client"]` a partir de ninguna cabecera. Efecto
  confirmado del revisor: correcto en el sentido de "no falsificable", pero
  si algo leyera `request.client.host` directamente sin pasar por
  `get_real_client_ip()`, vería siempre el mismo valor (el peer del edge)
  para todos los usuarios reales.

**Decisión**: no se revierte `forwarded_allow_ips` a `"*"` (eso reintroduce
el bypass original: cualquier cliente podría fijar `X-Forwarded-For` y
`ProxyHeadersMiddleware` lo tomaría como el peer real). En su lugar, tal
como sugiere el propio enunciado de esta tarea, `get_real_client_ip()` **no
depende de `ProxyHeadersMiddleware`** para nada: lee `X-Real-IP` directo de
`request.headers`, nunca de `request.client.host` reescrito por ese
middleware ASGI. Con la unificación del punto 4.4, los dos archivos que sí
leían `request.client.host` directamente ahora tampoco dependen de ese
middleware. `forwarded_allow_ips = "127.0.0.1"` se mantiene como red de
seguridad para cualquier código futuro que lea `request.client.host` sin
pasar por `get_real_client_ip()`: preferible que ese código vea un valor
uniforme pero no falsificable, a que vuelva a ver un valor falsificable por
cabecera (el problema original de la vuelta 0/1 con `"*"`).

**Advertencia metodológica confirmada durante la verificación de esta
vuelta** (afecta a cómo se deben leer TODAS las pruebas locales de este
documento, incluidas las de las vueltas anteriores): al ejecutar
`uvicorn app.main:app` **directamente** (sin gunicorn) para las pruebas
locales, `uvicorn.Config` activa su propio `ProxyHeadersMiddleware` con
`forwarded_allow_ips` por defecto `"127.0.0.1"` -- y como el peer TCP local
de las pruebas con `curl` **es** `127.0.0.1`, ese middleware SÍ confía y
reescribe `request.client.host` a partir de `X-Forwarded-For`, cosa que
**nunca** ocurre en producción real bajo gunicorn (donde el peer jamás es
`127.0.0.1`). Se detectó este artefacto durante la verificación de esta
misma vuelta (un ataque de registro con emails distintos parecía bypassear
el fix hasta darse cuenta de esto) y se corrigió arrancando el servidor de
pruebas con `--no-proxy-headers` para replicar fielmente el comportamiento
de producción (el peer nunca está en la lista de confianza). Todas las
pruebas de la sección 4.6 se ejecutaron ya con este ajuste. Se deja
documentado explícitamente porque **las pruebas de las vueltas 0 y 1 de
este mismo documento no mencionan haber tenido en cuenta este matiz** --
no se puede descartar que alguna de sus conclusiones locales se haya visto
afectada por este mismo artefacto de `uvicorn` ejecutado en modo standalone
sin `--no-proxy-headers`, aunque no cambia el veredicto final de ninguna de
ellas (los ataques documentados como exitosos en la sección 3 lo eran por
razones independientes de este matiz: single-value XFF list índex -1 == 0).

### 4.6 Verificación en vivo (exigente, todos los ataques reproducidos)

Backend local: `ENVIRONMENT=development DEBUG=true`,
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8031 --no-proxy-headers`
(venv compartido) -- ver 4.5 para por qué `--no-proxy-headers` es necesario
para que la prueba local sea representativa de producción. Confirmado vivo
con `GET /health` → `200`.

**1) Ataque MÁS SIMPLE (un único valor de `X-Forwarded-For`, sin lista de
dos) — login, mismo email en las 35 peticiones:**
```
for i in $(seq 1 35); do
  fakeip="10.$((RANDOM%255)).$((RANDOM%255)).$((RANDOM%255))"
  curl -s -o /dev/null -w "%{http_code} " -X POST http://127.0.0.1:8031/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-Forwarded-For: $fakeip" \
    -d "username=noexiste@test.com&password=wrongpass$i"
done
```
Resultado: intentos 1-30 → `401`; **intentos 31-35 → `429`**. Bypass
cerrado (antes: 35/35 `401`, cero `429`).

**2) Mismo ataque contra register (email DISTINTO en cada intento, como
haría un atacante real de spam de registro — 12 intentos):**
Resultado: intentos 1-10 → `422`; **intentos 11-12 → `429`**. Cerrado por
el fallback a `request.client.host` (constante, ya no influido por
`X-Forwarded-For`), sin necesitar siquiera la clave de cuenta.

**3) Mismo ataque contra checkout público (12 intentos, `customer_email`
distinto cada vez):**
Resultado: intentos 1-10 → `200` (PaymentIntent real creado); **intentos
11-12 → `429`**. Cerrado.

**4) Ataque con `X-Real-IP` falso y distinto en cada petición — login,
MISMO email en las 35 peticiones (prueba explícita de que la identidad
compuesta cierra el hueco incluso si la cabecera que SÍ se usa como fuente
primaria fuera perfectamente falsificable):**
```
for i in $(seq 1 35); do
  fakeip="172.16.$((RANDOM%255)).$((RANDOM%255))"
  curl ... -H "X-Real-IP: $fakeip" -d "username=noexiste@test.com&password=wrongpass$i"
done
```
Resultado: intentos 1-30 → `401`; **intentos 31-35 → `429`**. Bloqueado por
la clave de cuenta (`acct:auth_login:noexiste@test.com`), no por IP --
confirmado en los logs del servidor (`account_keyed=True` en las líneas de
`Rate limited request`).

**5) Mismo ataque de `X-Real-IP` falso, MISMO `customer_email` objetivo,
contra checkout (12 intentos):** intentos 1-10 → `200`; **intentos 11-12 →
`429`**. Cerrado por la misma clave de cuenta.

**6) Límite residual reconocido explícitamente — `X-Real-IP` falso Y
DISTINTO objetivo (email) en cada petición, register (12 intentos):**
```
for i in $(seq 1 12); do
  fakeip="172.16.$((RANDOM%255)).$((RANDOM%255))"
  curl ... -H "X-Real-IP: $fakeip" -d "{\"email\":\"residual$i@test.com\",...}"
done
```
Resultado: **12/12 → `422`, CERO `429`**. Mismo patrón contra checkout
público con `customer_email` distinto cada vez: **12/12 → `200`, CERO
`429`**. **Este caso NO queda cerrado por el fix de esta vuelta** -- se
reconoce explícitamente como limitación residual (ver 4.7).

**7) Camino legítimo (sin ninguna cabecera falsa) — login, register y
checkout, para confirmar que no hay regresión de comportamiento:**
- Login, 35 intentos: 30×`401` + 5×`429` -- idéntico a las vueltas
  anteriores.
- Register, 12 intentos: 10×`422` + 2×`429` -- idéntico.
- Checkout, 12 intentos: 10×`200` (PaymentIntent real en Stripe test) +
  2×`429` -- idéntico.

### 4.7 Limitaciones residuales reconocidas con total honestidad

1. **No se puede confirmar al 100 %, sin tráfico real contra el edge de
   Railway desplegado, que `X-Real-IP` sea efectivamente sobrescrito por
   Railway y no simplemente reenviado tal cual si el cliente ya lo manda.**
   Es la asunción más razonable disponible (coincide con la documentación
   oficial, a diferencia de la vuelta anterior), pero sigue siendo una
   asunción. Si resultara ser falsa, `get_real_client_ip()` seguiría siendo
   falsificable vía `X-Real-IP` -- exactamente el mismo tipo de riesgo que
   motivó añadir la identidad compuesta de cuenta (4.3), que no depende de
   esta asunción para el caso de un objetivo repetido.
2. **Un atacante que varíe SIMULTÁNEAMENTE la IP/cabecera reportada Y el
   objetivo (email) en cada petición sigue sin poder distinguirse de
   tráfico legítimo por identidad**, para `auth_register` y para el
   checkout público (para `auth_login` esto es menos relevante en la
   práctica: la única forma de que ese ataque "tenga sentido" contra login
   sería probar contraseñas contra una lista de cuentas reales conocidas
   variando también el email en cada intento, lo cual sigue estando
   limitado por bucket normal de IP salvo que la IP también sea
   perfectamente falsificable en cada petición). Reproducido y confirmado
   explícitamente en 4.6.6 como abierto. Cerrar esto por completo
   requeriría una de estas opciones, ninguna aplicada en esta vuelta por
   quedar fuera del alcance pedido (compounding de identidad, no
   infraestructura nueva):
   - Confirmación verificada (no asumida) de qué IPs concretas puede tener
     el edge de Railway, para validar criptográficamente el único hop de
     confianza -- no existe públicamente, a diferencia de p. ej. los
     rangos de Cloudflare.
   - Un límite global no atado a identidad por bucket (p. ej. N peticiones
     totales/minuto a `auth_register` o al checkout, sin importar IP/email)
     -- instrumento más burdo, con riesgo de falsos positivos bajo picos de
     tráfico legítimo reales, no añadido aquí para no introducir ese riesgo
     sin que el usuario lo decida explícitamente.
   - CAPTCHA / prueba de trabajo tras N intentos fallidos -- cambio de
     producto, no solo de infraestructura, fuera del alcance de esta
     tarea.
3. **El store de rate limit sigue en memoria por proceso**, no compartido
   entre réplicas/workers -- limitación ya documentada en la sección 1,
   sin cambios en esta vuelta.
4. **`get_real_client_ip()` puede devolver `"unknown"`** (antes `None` en
   `thalos_login_audit_middleware.py`/`checkin.py`) si no hay `X-Real-IP`
   ni `request.client` -- caso extremo no observado en las pruebas de este
   documento, considerado cosmético (ver 4.4).
5. **No se ha podido probar nada de esto contra el edge real de Railway
   desplegado** -- limitación que comparten las tres vueltas de este mismo
   documento. Toda la evidencia de 4.6 es contra un backend local, con la
   salvedad metodológica de 4.5 (`--no-proxy-headers`) aplicada
   explícitamente para que esa evidencia local sea representativa de la
   arquitectura de producción real (gunicorn + `forwarded_allow_ips`
   fijo + edge que nunca es el peer de confianza).

### 4.8 Verificación de regresión

```
C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe -m pytest tests -q
```
Ejecutado tras aplicar todos los cambios de esta vuelta (`security_middleware.py`,
`thalos_login_audit_middleware.py`, `checkin.py`, `gunicorn.conf.py`).
Resultado: **7 failed, 300 passed, 3 errors** -- idéntico al baseline citado
en las secciones 0/3 de este documento, mismos 7 tests y 3 errores
preexistentes (ninguno relacionado con rate limiting, extracción de IP, ni
con los endpoints tocados). Sin regresión.

### 4.9 Conclusión de esta vuelta

- El bypass crítico de rate limiting está corregido para el ataque más
  simple y más probable (un único valor de IP/cabecera falso por
  petición, sin necesidad de simular un segundo hop), verificado en vivo
  contra login, register y checkout, con `X-Forwarded-For` Y con
  `X-Real-IP` como vector de ataque, y sin regresión del camino legítimo.
- La identidad compuesta (cuenta/objetivo + IP) para `auth_login`,
  `auth_register` y `public_checkout_payment_intent` cierra el caso más
  realista y barato de ejecutar (repetir el ataque contra UN objetivo fijo)
  de forma robusta, sin depender de acertar qué cabecera usa Railway.
- Queda una limitación residual reconocida explícitamente y no cerrada en
  esta vuelta (4.7.2): variar simultáneamente IP y objetivo en cada
  petición contra `auth_register`/checkout. Se documenta con honestidad
  total en vez de reclamarse como cerrada -- corresponde al usuario decidir
  si esto bloquea el deploy o se acepta como riesgo residual conocido,
  dado que cerrarlo del todo requiere infraestructura (Redis compartido,
  límite global, CAPTCHA) fuera del alcance de esta tarea.
- Se unificó `thalos_login_audit_middleware.py` y `checkin.py` con la
  misma lógica de extracción de IP (cambio de bajo riesgo, sin superficie
  de autorización nueva), resolviendo el efecto secundario que el revisor
  señaló sobre `forwarded_allow_ips`.
- Sin regresión de tests (`7 failed, 300 passed, 3 errors`, idéntico al
  baseline).
- No se ha hecho push ni merge a `main`. Rama:
  `feature/consolidacion-final`. **Este es el tercer intento sobre el mismo
  hallazgo** (vuelta 0 → vuelta 1 devuelta → esta vuelta 2). Dado el
  historial de dos devoluciones previas, este commit necesita una TERCERA
  revisión independiente antes de considerar el hallazgo cerrado -- el
  propio ejecutor no se declara cerrado a sí mismo.

---

## 5. Tercera revision independiente (commit 5798be0) - VEREDICTO: APROBADO CON SALVEDAD EXPLICITA

Revisor: revisor-independiente. Commit auditado: 5798be0b88d71786e29dff60fd4dba7039df0dec
("fix(security): vuelta 2 - cerrar bypass real de rate limiting via IP
falsificada"). Este es el TERCER intento sobre el mismo hallazgo (vuelta 0
ee1f212 devuelta, vuelta 1 dbd0601 devuelta, esta es la vuelta 2). Dado el
historial, esta revision se hizo con el nivel de exigencia mas alto de las
tres: cada afirmacion del reporte se reprodujo de forma independiente contra
un backend levantado por mi propia cuenta (no se reutilizo ningun output
pegado en el documento), con datos propios y, en varios casos, con ataques
adicionales no descritos explicitamente por el ejecutor.

### 5.1 Reproduccion del "artefacto metodologico" (uvicorn sin --no-proxy-headers)

Confirmado como REAL, no como excusa. Levante dos servidores propios con el
venv compartido, mismo commit 5798be0:

- Puerto 8091: python -m uvicorn app.main:app --host 127.0.0.1 --port 8091
  (SIN --no-proxy-headers, el comportamiento por defecto).
- Puerto 8092/8093: mismo comando CON --no-proxy-headers.

Ataque: 12 intentos de POST /api/v1/auth/register, un X-Forwarded-For
aleatorio distinto por peticion (un solo valor, sin lista), email DISTINTO
en cada intento.

- Puerto 8091 (sin --no-proxy-headers): 12/12 -> 422, CERO 429. Bypass
  aparente.
- Puerto 8092 (con --no-proxy-headers): 10x422 + 2x429. Bloqueado
  correctamente.

Causa confirmada leyendo el codigo fuente instalado de uvicorn==0.29.0
(uvicorn/middleware/proxy_headers.py, ProxyHeadersMiddleware.__init__):
trusted_hosts por defecto es 127.0.0.1. Cuando el peer TCP de la prueba
local (curl contra 127.0.0.1) coincide con ese default, la propia libreria
de uvicorn reescribe scope client a partir de X-Forwarded-For incluso
aunque la aplicacion nunca lea esa cabecera -- y como get_real_client_ip()
cae a request.client.host cuando no hay X-Real-IP, ese valor reescrito se
filtra igualmente. En produccion (gunicorn, forwarded_allow_ips igual a
127.0.0.1, peer real = edge de Railway, nunca 127.0.0.1, confirmado en
railway.toml/Dockerfile raiz) esta reescritura nunca ocurre, asi que la
prueba con --no-proxy-headers es la que replica fielmente produccion, no la
que se ejecuto sin ese flag. Confirmo la advertencia del ejecutor: es
plausible que las vueltas 0 y 1 de este documento arrastraran este mismo
artefacto sin saberlo (no mencionan el flag en ninguna de sus pruebas), pero
no cambia sus veredictos: los bypasses que demostraron entonces eran reales
por una razon independiente de este matiz.

### 5.2 Ataque IP falsa mas objetivo FIJO en los 3 endpoints -- CONFIRMADO BLOQUEADO

Contra el servidor propio con --no-proxy-headers (puerto 8092/8093, replica
fiel de produccion), con datos 100 por ciento propios (nunca reutilice los
que aparecen en el documento):

- Login, X-Real-IP aleatorio distinto en cada peticion, MISMO
  username fixedtarget en las 35 peticiones: 30x401 + 5x429 (bloqueo en el
  intento 31, exactamente el limite configurado). Confirmado tambien con
  X-Forwarded-For de un solo valor en vez de X-Real-IP (servidor 8093,
  arrancado limpio): 30x401 + 5x429.
- Checkout publico, X-Real-IP aleatorio distinto, MISMO customer_email
  fijo: 10x200 + 2x429.

Ambos casos bloqueados por la clave de cuenta, no por IP -- consistente con
lo que reporta el ejecutor.

### 5.3 Ataque IP falsa mas objetivo DISTINTO cada vez -- CONFIRMADO ABIERTO y mas amplio de lo que enfatiza el reporte

Reproducido de forma independiente, servidor propio limpio,
--no-proxy-headers:

- Register, X-Real-IP aleatorio distinto mas email distinto en cada una de
  12 peticiones: 12/12 -> 422, CERO 429. Abierto, tal como admite el
  ejecutor.
- Checkout publico, mismo patron con customer_email distinto cada vez (12
  peticiones): 12/12 -> 200, PaymentIntent real creado cada vez, CERO 429.
  Abierto, tal como admite el ejecutor.
- Login (hallazgo adicional, no verificado explicitamente por el ejecutor
  con esta combinacion exacta pero coherente con su propio razonamiento en
  4.7.2): X-Real-IP aleatorio distinto mas username distinto en cada una de
  35 peticiones: 35/35 -> 401, CERO 429. Tambien abierto. El reporte de la
  vuelta 2 caracteriza este caso para login como menos relevante en la
  practica porque, segun su propio razonamiento, solo importa si la IP
  tambien fuera perfectamente falsificable en cada peticion -- mi prueba
  confirma exactamente esa condicion y el resultado es bypass total tambien
  en login, no solo en register/checkout. No cambia mi veredicto (ver 5.7)
  pero corrige la impresion de que login queda a salvo de esta variante: no
  queda a salvo, queda protegido solo mientras la IP reportada no sea
  trivialmente falsificable por peticion.

### 5.4 Verificacion independiente de la documentacion de Railway

Repeti la consulta del ejecutor con mi propio curl contra
https://docs.railway.com/networking/public-networking/specs-and-limits
(HTTP 200, 2026-08-28). Confirmado, no solo citado: la fila Request Headers
de la tabla Technical specifications documenta explicitamente X-Real-IP
para identificar la IP remota del cliente, junto con X-Forwarded-Proto,
X-Forwarded-Host, X-Railway-Edge, X-Request-Start, X-Railway-Request-Id,
X-Railway-Debug. X-Forwarded-For no aparece en ningun punto del documento
(busque el literal X-Forwarded-For sobre el HTML descargado: cero
coincidencias). Coincide exactamente con la cita del ejecutor en la
seccion 4.1. La limitacion honesta que el propio ejecutor reconoce (no hay
confirmacion de que Railway sobrescriba X-Real-IP en vez de solo anadirla
si falta) sigue sin poder verificarse sin trafico real contra el edge
desplegado -- no lo pude cerrar yo tampoco en este entorno.

### 5.5 Camino legitimo y regresion -- SIN CAMBIOS RESPECTO A LO REPORTADO

Contra el servidor propio (--no-proxy-headers, sin ninguna cabecera
falsa): Login 30x401 + 5x429, Register 10x422 + 2x429, Checkout 10x200 +
2x429 -- identico al comportamiento documentado en las secciones 0/1/3/4,
sin regresion de UX para trafico legitimo.

Suite completa, ejecutada por mi cuenta, no reutilizada del reporte, con el
venv compartido (backend/venv/Scripts/python.exe -m pytest tests -q).
Resultado obtenido: 7 failed, 300 passed, 34 warnings, 3 errors en 329.58s
-- mismos 7 tests y 3 errores citados en las secciones 0/3/4
(test_config_loading, test_default_flags_simulated,
test_audit_includes_ai_modules,
test_default_mode_is_simulation_for_heuristic_modules,
test_backup_requires_execution_and_backup_flags,
test_build_metadata_origin_mock, test_monitoring_cycle_respects_flags, y 3
NameError en test_app.py). Coincide exactamente con el baseline citado.
Sin regresion.

### 5.6 Codigo: confirmacion linea a linea

- security_middleware.py::get_real_client_ip() (lineas 39-131): confirmado
  que ya NO lee X-Forwarded-For en ningun punto de la funcion. Usa
  X-Real-IP primero, fallback a request.client.host, nunca None silencioso
  (fallback final unknown).
- check_rate_limit() (lineas 330-390): confirmado que construye una lista
  de claves con la de IP+identidad de siempre, y anade una clave de cuenta
  solo si hay account_key y el bucket esta en _ACCOUNT_KEYED_BUCKETS;
  bloquea si CUALQUIERA de las claves supera el limite y solo registra el
  intento actual en todas las claves si ninguna bloqueo -- logica
  correcta, sin ramas muertas del comportamiento anterior.
- thalos_login_audit_middleware.py linea 76 y checkin.py linea 77:
  confirmado que ambos usan get_real_client_ip() con el import correcto, y
  que ninguno sigue leyendo request.client.host directamente.
- gunicorn.conf.py linea 115: forwarded_allow_ips sigue en 127.0.0.1, sin
  cambios respecto a la vuelta 1 (correcto, no se revirtio al valor
  inseguro anterior). workers por defecto es 1 si no se fija
  WEB_CONCURRENCY -- la limitacion ya documentada de store en memoria por
  proceso no se agrava ni se resuelve en esta vuelta.

### 5.7 Criterio sobre la limitacion residual (punto 3 de la tarea de esta revision)

Se reproduce y se acepta como real la limitacion residual: un atacante que
varie simultaneamente la IP/cabecera reportada y el objetivo
(email/username) en cada peticion no queda bloqueado en ninguno de los 3
endpoints (incluido login, ver 5.3). Mi criterio, aplicado con el nivel de
exigencia maximo que pide esta tercera vuelta:

No es una vulnerabilidad critica que deba bloquear el cierre de este
hallazgo, y no se exige una Vuelta 3 solo por esto. Razones:

1. No viola ninguna regla no negociable de la skill (THALOS, aislamiento
   multi-tenant, logging real, migraciones) -- es un limite de defensa en
   profundidad adicional sobre una mitigacion que ya cierra el vector de
   ataque mas barato y mas probable (repetir contra un objetivo fijo).
2. El precondicionante de la limitacion residual es materialmente mas caro
   que el bypass original. Los bypasses de las vueltas 0 y 1 eran
   explotables con un solo proceso curl en un bucle, sin coste, dando
   bypass total del 100 por ciento. El residual de esta vuelta exige
   ademas que la cabecera de IP reportada sea realmente indistinguible de
   trafico legitimo peticion a peticion -- es decir, o bien la asuncion
   sobre X-Real-IP documentada por Railway resulta ser falsa (Railway
   reenvia sin sobrescribir), algo que contradice el proposito que la
   propia documentacion le atribuye a esa cabecera, o el atacante dispone
   de diversidad real de IPs de origen (botnet o proxies), un salto de
   sofisticacion cualitativo respecto a un curl en un bucle.
3. El impacto del residual es de tipo spam o ruido, no de fuga de datos ni
   de fraude directo. El endpoint de checkout no adjunta datos de tarjeta
   en esta llamada (create_payment_intent solo recibe amount,
   customer_email, description y metadata, confirmado en
   services/stripe_service.py lineas 65-100); un PaymentIntent creado sin
   confirmar no cobra nada y no es un vector de card testing por si mismo,
   aunque si genera objetos huerfanos en el dashboard de Stripe y consume
   cuota de API. El de register solo permite crear cuentas basura en la BD
   propia, sin acceso a datos de otros tenants.
4. Cerrar el residual del todo exige una decision de producto o infra
   ajena al alcance de corregir el bypass: un limite global no atado a
   identidad implica elegir un umbral con riesgo real de falsos positivos
   bajo picos legitimos (por ejemplo una campana de marketing generando
   altas reales en poco tiempo), decision que corresponde al usuario, no a
   un umbral arbitrario impuesto en una revision de seguridad.

Salvedad explicita de esta aprobacion: se recomienda, sin exigirse como
bloqueante, anadir en una tarea futura, no ligada a este mismo hallazgo
critico ya cerrado, un backstop global de baja prioridad -- por ejemplo un
techo de peticiones totales por minuto a auth_register y a
public_checkout_payment_intent sin depender de IP ni de cuenta (umbral
holgado, pensado solo para frenar rafagas masivas de bots, no trafico
humano normal) -- y, si el usuario tiene forma de confirmarlo, verificar
con trafico real contra el Railway desplegado si X-Real-IP es
efectivamente sobrescrito por el edge (la unica asuncion de todo este fix
que ninguna de las tres vueltas ha podido verificar con el entorno real).

### 5.8 Estado del repositorio

git status --short sobre el working tree: limpio, nada pendiente antes de
este commit de revision. Rama actual: feature/consolidacion-final, HEAD en
5798be0. main local y origin/main en 97b949a, sin tocar. No se ha hecho
push ni merge a main en esta revision.

### Veredicto: APROBADO, con salvedad explicita documentada (no bloqueante)

El hallazgo critico de bypass de rate limiting (bypass total explotable
con un solo proceso curl, sin ninguna precondicion, verificado en las
vueltas 0 y 1) esta corregido y verificado de forma independiente para el
ataque mas simple y mas probable (IP o cabecera falsa variando por
peticion contra un objetivo fijo, y tambien contra un objetivo variable
cuando la IP reportada permanece estable, que es el comportamiento real
esperado en produccion bajo gunicorn). Persiste una limitacion residual,
tambien verificada de forma independiente y confirmada mas amplia de lo
que el propio reporte enfatiza (afecta tambien a login, no solo a
register o checkout, bajo la misma precondicion), pero se acepta como
riesgo residual de menor severidad, no critico, dado que exige un salto
de sofisticacion del atacante cualitativamente mayor que el bypass
original y su impacto es de tipo spam o ruido, no de fuga de datos,
fraude directo, ni bypass de THALOS o de aislamiento multi-tenant. Se
recomienda, sin bloquear el cierre de este hallazgo, un backstop global
de baja prioridad como tarea de hardening futura independiente. Sin
regresion de tests (7 failed, 300 passed, 3 errors, verificado por mi
cuenta, identico al baseline). Repositorio limpio, sin push ni merge a
main.
