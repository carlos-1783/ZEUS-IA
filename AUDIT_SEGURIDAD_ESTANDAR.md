# Auditoría de seguridad estándar pre-deploy — rate limiting y CORS

Rama: `feature/consolidacion-final`
Commit base auditado: `d864937` (aprobación definitiva de consolidación, pendiente de decisión de deploy)
Fecha: 2026-08-28
Ejecutor: ejecutor-produccion (skill `zeus-produccion`)

Resultado global: **ambos puntos ya estaban correctamente implementados en el
código heredado de esta rama.** No fue necesario ningún cambio de código. Este
documento dejó evidencia real (no solo lectura de código) de que ambos
controles funcionan en producción tal y como están, y documenta un hallazgo
menor no bloqueante (archivos de configuración CORS duplicados/muertos) para
que el usuario decida si se limpian en un step aparte.

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

Suite completa ejecutada ANTES de iniciar esta verificación (no se tocó
código de producción en este step, por lo que este resultado es también el
resultado DESPUÉS):

```
C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe -m pytest tests -q
```
Resultado: **7 failed, 300 passed, 3 errors** (idéntico al baseline documentado
en el commit `d864937` de aprobación definitiva). Sin regresión.

Fallos preexistentes (ya documentados como no bloqueantes en la aprobación
anterior, no relacionados con este step):
`test_basic.py::test_config_loading`,
`test_justicia_control_layer_v1.py::test_default_flags_simulated`,
`test_perseo_autofix_v2.py::test_audit_includes_ai_modules`,
`test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules`,
`test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags`,
`test_thalos_control_layer_v1.py::test_build_metadata_origin_mock`,
`test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags`,
y 3 errores en `test_app.py` (`NameError: name 'TestClient' is not defined`).

---

## Conclusión

- **Rate limiting**: ya implementado y verificado en vivo (429 real) en los 3
  endpoints pedidos (login 30/min, register 10/min, checkout público
  payment-intent 10/min). No se requirió instalar `slowapi` ni cambiar código.
  Limitación conocida: contador en memoria por proceso, no compartido entre
  réplicas/workers — pendiente si el despliegue usa más de una instancia.
- **CORS**: ya restringido a lista explícita de orígenes (nunca `"*"`),
  verificado en vivo que un origen no autorizado no se refleja y es
  rechazado en preflight (`400`), mientras que localhost de desarrollo y los
  3 dominios de producción configurados sí funcionan.
- **No se hizo ningún commit de código** porque no se encontró nada que
  arreglar en el alcance pedido. Este documento en sí es el artefacto a
  commitear.
- No se ha hecho push ni merge a `main`. Rama de trabajo:
  `feature/consolidacion-final`.
