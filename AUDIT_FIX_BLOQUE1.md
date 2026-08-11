# AUDIT_FIX_BLOQUE1 — Corrección de hallazgos críticos de seguridad

Rama: `feature/fix-seguridad-critica` (creada desde `main`).
Fuente de los hallazgos: auditoría real del núcleo en `feature/auditoria-real-nucleo`.
Alcance: **solo** los 4 hallazgos listados abajo. No se ha tocado nada de
esquema/multi-tenant a nivel de modelos, ni `zeus_core.py`/`zeus_agents.py`,
ni ningún otro archivo fuera de esta lista.

---

## 1. `GET/POST /api/v1/google/*` sin autenticación

**Archivo**: `backend/app/api/v1/endpoints/google.py`
**Commit**: `61b87c6`

### Qué cambié
Añadí `current_user: User = Depends(get_current_active_user)` a los 10
endpoints del router (`calendar/event`, `calendar/events`, `gmail/send`,
`gmail/inbox`, `drive/upload`, `drive/files`, `sheets/create`,
`sheets/write`, `sheets/read`, `status`), reutilizando el mismo import
(`app.core.auth.get_current_active_user`) que ya usan otros endpoints del
proyecto (p. ej. `metrics.py`). No se creó ningún mecanismo de auth nuevo.

(Nota: el hallazgo original decía "9 endpoints"; al auditar el archivo
resultaron ser 10 rutas — se protegieron las 10.)

### Cómo lo probé
Levanté el backend en local (`uvicorn app.main:app`, SQLite de prueba) y until
usé `curl` real:

- Sin token: `GET /api/v1/google/status` → **401** `{"detail":"No se pudieron
  validar las credenciales"}`. Igual para `GET /api/v1/google/drive/files`.
- Con token válido (usuario registrado y logueado vía `/api/v1/auth/login`):
  `GET /api/v1/google/status` → **200** (llega a la lógica real).
  `GET /api/v1/google/drive/files` → **500** `"Google Drive not configured"`
  (correcto: pasa la auth y falla honestamente porque no hay credenciales de
  Google en `.env`, tal como confirmó la auditoría original).

### Resultado
✅ Corregido y verificado end-to-end por HTTP. No se detectó ningún flujo
existente (frontend ni tests) que dependiera de acceder a estos endpoints sin
token.

---

## 2. `POST /api/v1/onboarding/create-account` sin verificar el pago

**Archivo**: `backend/app/api/v1/endpoints/onboarding.py`
**Commit**: `207afba`

### Qué cambié
Añadí `_verify_stripe_payment_completed(payment_intent_id)`, que reutiliza
la misma llamada que ya usaba `GET /verify-payment/{id}`
(`stripe.PaymentIntent.retrieve`), y la invoco **antes** de crear cualquier
registro de usuario en `create_account_after_payment`. Rechaza con:
- `400` si no se envía `payment_intent_id`.
- `503` si Stripe no está configurado (no se puede verificar → no se activa
  la cuenta).
- `402` si Stripe no reconoce el pago o su estado no es `succeeded`.

Ninguna cuenta se crea (`is_active=True`) sin que esta verificación pase.

### Cómo lo probé
Con `STRIPE_API_KEY` de test (`sk_test_...`, confirmé el prefijo sin exponer
la clave) hice pruebas reales contra la API de Stripe, no simuladas:

1. **Sin `payment_intent_id`** → `400 "payment_intent_id requerido..."`.
   Confirmé que no se creó ninguna cuenta (login posterior con ese email
   devuelve "Incorrect email or password").
2. **`payment_intent_id` inventado** (`pi_FAKE_NOT_REAL_123`) → `402`, con el
   error real devuelto por Stripe: `"No such payment_intent"` (la llamada
   llegó de verdad a la API de Stripe, request id real en la respuesta).
3. **Flujo feliz**: creé y confirmé un `PaymentIntent` real en modo test de
   Stripe (`pm_card_visa`, `status: succeeded`) y llamé a
   `create-account` con ese id → `201 Created`, cuenta creada correctamente.
   Esto confirma que el fix no rompe el flujo legítimo.

### Resultado
✅ Corregido y verificado end-to-end contra la API real de Stripe (modo
test), con los 3 casos: rechazo sin dato, rechazo con dato falso, y éxito
con pago real confirmado.

---

## 3. `GET /api/v1/metrics/dashboard` sin auth y sin filtro de tenant

**Archivo**: `backend/app/api/v1/endpoints/metrics.py`
**Commit**: `9141c71`

### Qué cambié
Añadí `current_user: User = Depends(get_current_active_user)` y filtré las
consultas a `AgentActivity` (la actividad y la comparación de tendencia con
el período anterior) por `AgentActivity.user_email == current_user.email`.

Usé este campo y no `company_id` porque, tal como documentó la auditoría de
capa BD (`feature/auditoria-real-nucleo`), el modelo `AgentActivity` **no
tiene columna `company_id`/`tenant_id`** — y tocar el modelo está fuera de
alcance de este bloque. `user_email` es exactamente el mismo patrón que ya
usan los endpoints hermanos `/performance` y `/summary` en este mismo
archivo, así que el fix queda consistente con el resto del módulo en vez de
inventar un criterio nuevo.

### Cómo lo probé
- Sin token: `GET /api/v1/metrics/dashboard` → **401**. Antes del fix este
  mismo endpoint devolvía `200` con datos agregados de todos los tenants sin
  pedir nada.
- Registré dos usuarios de tenants distintos, cada uno con su propia
  actividad real generada por el sistema (arranque, automatización).
  - Usuario A (token propio) → `total_interactions: 4`, `cost_savings: €200`.
  - Usuario B, otro tenant (token propio) → `total_interactions: 3`,
    `cost_savings: €50`.
  Los números son distintos entre ambos y ninguno ve el total agregado del
  otro — confirma aislamiento real, no solo que "algo cambió".

### Resultado
✅ Corregido y verificado con dos tenants reales distintos.

---

## 4. `GET /api/v1/invoices/` y `get_invoice_or_404` sin filtro de tenant (IDOR)

**Archivo**: `backend/app/api/v1/endpoints/invoices.py`
**Commit**: `36b38fd`

### Qué cambié
- `list_invoices`: añadí un filtro `or_(Invoice.company_id.in_(allowed),
  and_(Invoice.company_id.is_(None), Invoice.created_by == current_user.id))`,
  usando `crm_svc.company_ids_for_user(db, current_user)` — el mismo helper
  que ya usa `services/crm_office_service.py` para CRM/oficina — más un
  fallback para facturas legacy sin `company_id` creadas por el propio
  usuario (para no romper datos antiguos).
- `get_invoice_or_404`: sustituí el comentario que admitía "verificación de
  organización no implementada" por la comprobación real: si
  `invoice.company_id` no está entre las empresas del usuario (y no es una
  factura legacy suya), lanza `403 Forbidden` — el mismo código que el
  docstring de la función ya prometía pero nunca ejecutaba.

### Cómo lo probé — y por qué no fue 100% por HTTP (importante, léase)

Durante la verificación encontré **dos bugs preexistentes y no relacionados**
que impiden probar este endpoint completo por HTTP tal cual está en `main`
hoy, y que **no** he tocado por estar fuera del alcance de este bloque:

1. `invoices.py`, `products.py` y `customers_fixed.py` usan
   `app.core.security.get_current_active_user` (no
   `app.core.auth.get_current_active_user`, que es el que sí funciona y usan
   `google.py`/`metrics.py`). Esa función decodifica el JWT pasando
   `audience=settings.JWT_AUDIENCE`, que es una **lista**
   (`["zeus-ia:auth", "zeus-ia:access", "zeus-ia:websocket"]`) a
   `jose.jwt.decode()`, que solo acepta un string. Resultado: **todo token,
   válido o no, es rechazado con 401** en cualquier endpoint que use este
   import — confirmado reproduciendo el `JWTError: audience must be a string
   or None` directamente. Esto ya estaba roto en `main` antes de mi cambio;
   lo confirmé haciendo `git stash` de mis 4 commits y comprobando que el
   fallo persiste igual.
2. `get_invoice_or_404` (líneas ya existentes, no tocadas por mí) hace
   `joinedload(Invoice.customer)`, pero esa relación está comentada en el
   modelo (`app/models/erp.py:171`, *"TEMPORALMENTE COMENTADO PARA EVITAR
   ERROR DE IMPORTACIÓN CIRCULAR"*, ya detectado en la auditoría original).
   Eso hace que la función lance `AttributeError` en **cualquier** llamada,
   independientemente de mi fix.

Ambos son hallazgos nuevos, reales, y candidatos claros para el próximo
bloque — los dejo documentados aquí en vez de arreglarlos, tal como pide la
regla de "no arregles nada fuera de esta lista".

Para verificar mi cambio sin depender de esos dos bugs ajenos, probé la
lógica real (mismo código, mismas funciones `crm_office_service`, misma
sesión de BD SQLAlchemy real) directamente en proceso, sin pasar por el
transporte HTTP roto:

- **Aislamiento en `list_invoices`**: repliqué literalmente el filtro que
  añadí y lo ejecuté contra dos facturas reales de dos tenants reales en la
  BD de prueba → usuario A solo ve su factura (id 1), usuario B (otro
  tenant) solo ve la suya (id 2). Antes del fix ambos habrían visto las dos.
- **`get_invoice_or_404` (llamando a la función real importada del módulo,
  sin reescribirla, solo evitando el `joinedload` roto para poder llegar
  a mi código)**:
  - Usuario B pidiendo la factura de usuario A → `403 Forbidden
    "No tienes permiso para acceder a esta factura"`.
  - Usuario A pidiendo su propia factura → `200`, la devuelve.
- Confirmado por HTTP (esto sí funciona igual con o sin mi fix, porque el
  bug de auth es previo a llegar a mi código): `GET /api/v1/invoices/` sin
  token → **401** (esto ya era así antes, se mantiene).

### Regresión — suite de tests completa
Corrí los 226 tests de `backend/tests/` dos veces: una con mis 4 commits
aplicados, otra con `git stash` (código de `main` sin mis cambios).
Resultado **idéntico** en ambos casos: `7 failed, 214 passed, 2 skipped, 3
errors` (las mismas 10 fallas/errores exactas, ninguna relacionada con
`google.py`, `onboarding.py`, `metrics.py` ni `invoices.py` — son fallos
preexistentes en `test_basic.py`, `test_justicia_control_layer_v1.py`,
`test_perseo_autofix_v2.py`, `test_thalos_control_layer_v1.py`,
`test_thalos_safe_v1.py` y `test_app.py`). Mis cambios no rompieron ni
arreglaron ningún test existente.

### Resultado
✅ Lógica de aislamiento corregida y verificada a nivel de función/BD real.
⚠️ No se pudo verificar el flujo HTTP completo de `get_invoice_or_404`
porque dos bugs preexistentes y no relacionados lo bloquean por completo
(ver arriba) — recomendado abrirlos como hallazgos para el próximo bloque.

---

## Resumen

| # | Hallazgo | Archivo | Commit | Verificado por HTTP real | Pendiente |
|---|---|---|---|---|---|
| 1 | Sin auth en `/google/*` | `google.py` | `61b87c6` | Sí (401/200/500) | — |
| 2 | Sin verificar pago en onboarding | `onboarding.py` | `207afba` | Sí (Stripe test mode real: 400/402/201) | — |
| 3 | Sin auth/filtro en `/metrics/dashboard` | `metrics.py` | `9141c71` | Sí (401 + aislamiento entre 2 tenants) | — |
| 4 | Sin filtro de tenant en `/invoices/` (IDOR) | `invoices.py` | `36b38fd` | Parcial (lógica verificada en proceso; transporte HTTP bloqueado por 2 bugs preexistentes no tocados) | Arreglar `app.core.security.get_current_active_user` (bug de `audience` tipo lista) y la relación `Invoice.customer` comentada — ambos fuera de alcance de este bloque |

**No se hizo merge a `main`. No se hizo push.** La rama
`feature/fix-seguridad-critica` queda lista con 4 commits atómicos para
revisión y PR.
