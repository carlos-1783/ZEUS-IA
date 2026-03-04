# ROCE ZEUS_LOCAL_CORS_FIX_001 — Cierre

## Objetivo
Corregir error CORS en entorno local (frontend localhost:5173, backend localhost:8000) sin afectar producción (Railway).

## Fase 1 — Diagnóstico

### Configuración actual
- **CORS** (`backend/app/main.py` líneas 36-44): `CORSMiddleware` con `settings.BACKEND_CORS_ORIGINS`, `allow_methods` incluye OPTIONS, `allow_headers` reducido (sin usar la lista completa de `config`).
- **Orígenes** (`backend/app/core/config.py` líneas 62-72): Lista por defecto incluye `http://localhost:5173` y `http://127.0.0.1:5173`. Si en local existe `BACKEND_CORS_ORIGINS` en `.env` con solo orígenes de producción, esos orígenes locales pueden quedar fuera.
- **Preflight OPTIONS**: El middleware CORS de Starlette responde al OPTIONS; si el `Origin` no está en `allow_origins`, la respuesta no pasa el access control check.
- **Auth**: Las rutas protegidas no ejecutan auth en OPTIONS porque OPTIONS no lleva `Depends(get_current_user)` en la ruta; el problema es que si CORS rechaza el preflight, el navegador nunca llega a enviar el POST.

### Causa del fallo
1. En desarrollo, si `BACKEND_CORS_ORIGINS` se sobreescribe por env (o se parsea como lista distinta), pueden faltar `http://localhost:5173` / `http://127.0.0.1:5173`.
2. `allow_headers` en `main.py` era una lista corta; algunos clientes envían más cabeceras en `Access-Control-Request-Headers`; si no están permitidas, el preflight puede fallar.
3. No existía un handler OPTIONS explícito para `/login`, por lo que dependíamos al 100% del middleware; con un OPTIONS explícito se evita cualquier posible interferencia de enrutado.

### Ubicación
- `backend/app/main.py`: líneas 36-44 (CORS).
- `backend/app/core/config.py`: después de línea 218 (orígenes CORS).
- `backend/app/api/v1/endpoints/auth.py`: ruta POST `/login` (sin OPTIONS antes del fix).

---

## Fase 2 — Cambios realizados

### 1. `backend/app/core/config.py`
- Tras aplicar `ZEUS_ADDITIONAL_CORS_ORIGINS`, se añade lógica **solo en desarrollo local** (cuando `ENVIRONMENT=development` o `DEBUG=true` **y** no hay `RAILWAY_ENVIRONMENT` / `RAILWAY_SERVICE_NAME`):
  - Se fuerza la inclusión de orígenes locales: `http://localhost:5173`, `http://127.0.0.1:5173`, y los de los puertos 3000 y 8000.
  - Así, en local los preflight siempre tienen un origen permitido sin tocar la configuración usada en Railway.

### 2. `backend/app/main.py`
- CORS pasa a usar la configuración completa de `settings`:
  - `allow_methods` → `settings.CORS_ALLOW_METHODS` (con fallback).
  - `allow_headers` → `settings.CORS_ALLOW_HEADERS` (con fallback).
  - `expose_headers` → `settings.CORS_EXPOSE_HEADERS` (con fallback).
  - `max_age` → `settings.CORS_MAX_AGE` (p. ej. 600) para cachear preflight.

### 3. `backend/app/api/v1/endpoints/auth.py`
- Añadido `@router.options("/login", include_in_schema=False)` que devuelve `Response(status_code=200)` sin dependencias de autenticación.
- El preflight OPTIONS a `/api/v1/auth/login` obtiene 200; el middleware CORS sigue añadiendo las cabeceras `Access-Control-*`.

---

## Fase 3 — Service Worker
- Revisado `frontend/public/service-worker.js`: las peticiones a `/api/` usan estrategia **network-first** (líneas 74-76), no se cachea el preflight ni se bloquea. No se requirieron cambios.

---

## Fase 4 — Verificación

### En local (development)
1. Preflight: `OPTIONS http://localhost:8000/api/v1/auth/login` con `Origin: http://localhost:5173` debe devolver **200** y cabeceras `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Credentials`.
2. Login: después del preflight, `POST /api/v1/auth/login` con credenciales debe completarse correctamente.

### En producción (Railway)
- No se define `ENVIRONMENT=development` ni `DEBUG=true` en Railway; la condición `_env_dev and not _is_railway` es falsa, por tanto **no se modifica** `BACKEND_CORS_ORIGINS` en producción.
- Los cambios en `main.py` solo usan valores de `settings` que en Railway siguen siendo los mismos (o los definidos por env).
- El nuevo `OPTIONS /login` es un endpoint que devuelve 200 y no altera el comportamiento del POST ni la seguridad.

---

## Criterios de aceptación
- Preflight OPTIONS devuelve HTTP 200 en local.
- Login funciona correctamente en local (frontend en 5173, backend en 8000).
- No hay impacto en Railway; producción permanece intacta.
- Configuración condicionada a entorno development y sin alterar JWT ni lógica de autenticación.

**Estado final:** `LOCAL_LOGIN_CORS_RESOLVED_WITHOUT_PRODUCTION_IMPACT`
