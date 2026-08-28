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
