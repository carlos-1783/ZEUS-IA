# Informe de verificación de producción — ZEUS-IA

**Fecha:** 2026-03-12  
**Checklist:** `zeus_production_readiness_check.json` (creado a partir de auditorías existentes)  
**Alcance:** Verificación contra código fuente real; evidencia por archivo:línea.

---

## 1. SEGURIDAD (verificación completa)

| Id    | Descripción                                              | Estado   | Evidencia |
|-------|----------------------------------------------------------|----------|-----------|
| SEC-1 | SECRET_KEY/JWT desde variable de entorno                 | **WARNING** | `backend/app/core/config.py:38` — `os.getenv("SECRET_KEY", "dev_default_...")`; en producción debe fijarse env. |
| SEC-2 | Contraseñas hasheadas (bcrypt/passlib)                   | **PASSED**  | `backend/app/core/security.py:22` (CryptContext bcrypt), `:574-584` (verify_password, get_password_hash). |
| SEC-3 | CORS lista de orígenes (no *)                            | **PASSED**  | `backend/app/main.py:39-46`, `backend/app/core/config.py:65-75` — `BACKEND_CORS_ORIGINS` lista explícita. |
| SEC-4 | Protección SQL injection (ORM/parametrizado)             | **PASSED**  | `backend/app/core/auth.py:44` (User.email == email_normalized); migración `db/base.py` usa dict fijo. |
| SEC-5 | Rutas protegidas con autenticación                       | **PASSED**  | Múltiples endpoints usan `Depends(get_current_active_user)` o `get_current_active_superuser` (tpv, admin, auth, etc.). |
| SEC-6 | Rate limiting en auth (login/register)                    | **FAILED**  | `backend/app/core/security_middleware.py:87-96` define límite para `/api/v1/auth/login`; **no está montado** en `app/main.py` (solo CORSMiddleware). |
| SEC-7 | No exponer datos sensibles en logs                       | **WARNING** | `backend/app/core/security.py:243` — `logger.error(f"Token recibido: {token}")`; `onboarding.py:315`, `webhooks.py:174` — `print(temp_password)`. |

---

## Resumen de estados

| Estado   | Cantidad |
|----------|----------|
| **PASSED**  | 4 |
| **WARNING** | 2 |
| **FAILED**  | 1 |

---

## Decisión: ¿LISTO PARA PRODUCCIÓN?

**NO**, con la configuración actual.

- Hay **1 FAILED** (rate limiting de auth no activo).
- Hay **2 WARNING** (SECRET_KEY por defecto y logs con token/contraseña temporal).

Para considerar el sistema listo para producción es necesario al menos:
- Activar el rate limiting en login/register, **o** documentar y aceptar el riesgo.
- Asegurar SECRET_KEY (y REFRESH_TOKEN_SECRET) por entorno en producción.
- Evitar registrar el token completo y contraseñas temporales en logs/prints.

---

## Acciones prioritarias (si NO está listo)

1. **Prioridad alta — Rate limiting**
   - Montar `SecurityMiddleware` en `backend/app/main.py` (p. ej. `app.add_middleware(SecurityMiddleware)` o el patrón que use el proyecto) para que aplique el límite a `/api/v1/auth/login` y `/api/v1/auth/register`.
   - Evidencia actual: `backend/app/core/security_middleware.py:87-96` (límites definidos); `backend/app/main.py` (solo CORS).

2. **Prioridad alta — SECRET_KEY en producción**
   - En Railway (o el entorno de producción) definir `SECRET_KEY` y `REFRESH_TOKEN_SECRET`; no depender del valor por defecto de `config.py`.
   - Evidencia: `backend/app/core/config.py:38,52`.

3. **Prioridad media — Logs sensibles**
   - En `backend/app/core/security.py` línea 243: no registrar el token completo; por ejemplo registrar solo `token[:10]+'...'` o eliminar la línea en producción.
   - En `backend/app/api/v1/endpoints/onboarding.py:315` y `webhooks.py:174`: sustituir `print(temp_password)` por logger sin contraseña o eliminar en producción.

4. **Opcional**
   - Revisar que en producción no se use `DEBUG=True` para no aumentar superficie de información en logs y respuestas.

---

*Checklist detallado en `zeus_production_readiness_check.json`. Sección 1 (Seguridad) verificada contra el código indicado.*
