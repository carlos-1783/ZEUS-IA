# ROCE — Auditoría Final de Producción | ZEUS-IA

**Rol:** System Auditor  
**Fecha:** 2026-01-23  
**Objetivo:** Determinar exactamente qué falta para que ZEUS opere en PRODUCCIÓN REAL sin simulaciones, con cobro activo y automatización persistente.  
**Regla:** Solo hechos verificables. Sin suposiciones. Sin proteger al sistema.

---

## 1. Estado real del sistema

ZEUS-IA está desplegado en Railway con variables de entorno configuradas. El CORE funciona: agentes razonan, TeamFlow escribe actividades en BD (`agent_activities`), el executor procesa actividades pendientes cada 600 segundos, y `POST /actions/execute` está implementado con bloqueo cuando no hay handler. **Sin embargo**, múltiples `action_type` de los workflows de TeamFlow **no tienen handler** y se bloquean con `blocked_missing_handler` en lugar de ejecutarse. Las integraciones externas (Stripe, Twilio, SendGrid) tienen código funcional pero **no persisten automáticamente** el resultado de webhooks en BD. El flujo de pago crea `PaymentIntent` pero el webhook de Stripe **no actualiza** el estado del usuario/empresa en BD tras el pago exitoso.

---

## 2. Qué funciona en producción

| Componente | Estado | Verificación |
|------------|--------|--------------|
| **CORE** | Funciona | Agentes razonan, TeamFlow orquesta, executor procesa actividades |
| **BD Activity Write** | Funciona | `ActivityLogger.log_activity()` escribe en `agent_activities` |
| **POST /actions/execute** | Funciona | Endpoint implementado, requiere SUPERUSER, bloquea si no hay handler |
| **Handlers reales** | Funcionan | PERSEO (task_assigned), RAFAEL (task_assigned), JUSTICIA (task_assigned, document_reviewed, compliance_check), AFRODITA (task_assigned), THALOS (security_scan, task_assigned→alerts, backup_created), ZEUS (coordination, task_delegated), GENERIC_INTERNAL (5 action_types) |
| **Stripe Service** | Funciona si configurado | `stripe_service.create_payment_intent()` funciona si `STRIPE_API_KEY` está en Railway |
| **Twilio Service** | Funciona si configurado | `whatsapp_service.send_message()` funciona si `TWILIO_ACCOUNT_SID` y `TWILIO_AUTH_TOKEN` están en Railway (por defecto sandbox) |
| **SendGrid Service** | Funciona si configurado | `email_service.send_email()` funciona si `SENDGRID_API_KEY` está en Railway |
| **Webhooks endpoints** | Existen | `POST /integrations/stripe/webhook`, `POST /integrations/whatsapp/webhook`, `POST /integrations/email/webhook` |
| **TPV** | Funciona | Productos, ventas, tickets, persistencia en BD |
| **Control Horario** | Funciona | Check-in/out, empleados, cálculo de horas |
| **Dashboard/Métricas** | Funciona | Lee `agent_activities`, calcula métricas reales |
| **Autenticación** | Funciona | JWT, refresh automático, roles |

---

## 3. Qué NO funciona y por qué

| Problema | Causa técnica | Impacto |
|----------|--------------|---------|
| **Action types sin handler se bloquean** | `invoice_sent` (RAFAEL), `contract_generator` (JUSTICIA), `document_signed` (JUSTICIA), `contract_creator_rrhh` (AFRODITA), `image_analyzer` (PERSEO), `ads_campaign_builder` (PERSEO) no están en `HANDLER_MAP`. `resolve_handler()` devuelve `None` → `run_workspace_task()` devuelve `status: "blocked_missing_handler"`. | Workflows `invoice_flow_v1`, `contract_sign_v1`, `rrhh_onboarding_v1`, `ads_launch_v1` **se bloquean** en pasos críticos. No hay ejecución real, solo actividades bloqueadas en BD. |
| **Stripe webhook no persiste en BD** | `POST /integrations/stripe/webhook` llama `stripe_service.process_webhook()` que devuelve `{"success": True, "event": "payment_succeeded"}` pero **no escribe** en BD el estado del pago. No actualiza `User` ni crea registro de transacción. | Si un cliente paga, el webhook recibe el evento pero **no se guarda** en BD. El onboarding no puede verificar el pago automáticamente. Requiere verificación manual o llamada a `GET /onboarding/verify-payment/{payment_intent_id}`. |
| **Twilio en sandbox por defecto** | `whatsapp_service.__init__()` usa `TWILIO_WHATSAPP_NUMBER` con default `"whatsapp:+14155238886"` (sandbox). Si no se configura explícitamente un número de producción, está en sandbox. | Mensajes solo funcionan con números verificados en sandbox. En producción real requiere número de WhatsApp Business aprobado y configurado. |
| **Email no persiste estado de envío** | `email_service.send_email()` devuelve `{"success": True, "status_code": 202}` pero **no escribe** en BD que se envió un email. No hay registro de comunicaciones. | No hay auditoría de emails enviados. No se puede verificar qué emails se enviaron a qué clientes. |
| **TeamFlow crea actividades pero muchas se bloquean** | `teamflow_engine.run_workflow()` crea `AgentActivity` con `status="pending"` o `"in_progress"` para cada paso. El executor las procesa, pero si no hay handler → `blocked_missing_handler`. | Workflows completos **no terminan** porque pasos críticos se bloquean. No hay ejecución end-to-end real de workflows completos. |
| **Permisos solo SUPERUSER en /actions/execute** | `POST /actions/execute` requiere `is_superuser=True`. No hay capa de permisos por `(agent, action_type)`. Cualquier superuser puede ejecutar cualquier acción. | No hay control granular. Un superuser puede ejecutar acciones que deberían estar restringidas. |

---

## 4. Bloqueantes reales antes de cobrar

### BLOQUEANTE #1: Stripe webhook no persiste pago en BD
**Qué falta:** Después de `stripe_service.process_webhook()` detectar `payment_intent.succeeded`, escribir en BD:
- Actualizar `User` con `stripe_customer_id`, `stripe_subscription_id` (si aplica)
- Crear registro de transacción/pago en tabla `payments` o similar
- Marcar onboarding como "pago verificado"

**Impacto:** Sin esto, **no puedes cobrar automáticamente**. Cada pago requiere verificación manual.

**Ubicación:** `backend/app/api/v1/endpoints/integrations.py` línea 227-249 (`stripe_webhook`)

---

### BLOQUEANTE #2: Action types críticos sin handler
**Qué falta:** Implementar handlers para:
- `invoice_sent` (RAFAEL) → generar factura real, persistir en BD
- `contract_generator` (JUSTICIA) → generar contrato, persistir en BD
- `document_signed` (JUSTICIA) → firmar documento, persistir hash
- `contract_creator_rrhh` (AFRODITA) → generar contrato laboral, persistir
- `image_analyzer` (PERSEO) → analizar imagen, persistir resultado
- `ads_campaign_builder` (PERSEO) → crear plan de campañas, persistir

**Impacto:** Workflows `invoice_flow_v1`, `contract_sign_v1`, `rrhh_onboarding_v1`, `ads_launch_v1` **no ejecutan** pasos críticos. Se bloquean.

**Ubicación:** `backend/services/automation/handlers/` → crear nuevos handlers o extender existentes

---

### BLOQUEANTE #3: Twilio en sandbox (no producción real)
**Qué falta:** Configurar `TWILIO_WHATSAPP_NUMBER` con número de WhatsApp Business real (no sandbox). Verificar que Twilio tiene aprobación para producción.

**Impacto:** Mensajes solo funcionan con números verificados en sandbox. En producción real **no funciona** hasta tener número aprobado.

**Ubicación:** Variable de entorno `TWILIO_WHATSAPP_NUMBER` en Railway

---

### BLOQUEANTE #4: Email no auditable
**Qué falta:** Después de `email_service.send_email()`, escribir en BD:
- Registro de email enviado (tabla `email_log` o similar)
- Destinatario, asunto, fecha, status_code

**Impacto:** No hay auditoría de comunicaciones. No puedes verificar qué se envió a quién.

**Ubicación:** `backend/services/email_service.py` método `send_email()`

---

### BLOQUEANTE #5: Onboarding no completa automáticamente tras pago
**Qué falta:** Cuando Stripe webhook detecta `payment_intent.succeeded`, **automáticamente**:
- Crear usuario en BD
- Enviar email con credenciales
- Activar cuenta

**Impacto:** Cada cliente requiere activación manual después del pago. No hay onboarding automático.

**Ubicación:** `backend/app/api/v1/endpoints/integrations.py` `stripe_webhook` → llamar lógica de `onboarding.py`

---

## 5. Acción única recomendada para desbloquear ZEUS al 100%

**Implementar handler de webhook de Stripe que persista pago y active onboarding automático.**

**Flujo exacto:**
1. `POST /integrations/stripe/webhook` recibe `payment_intent.succeeded`
2. Extraer `payment_intent_id`, `customer_email`, `amount`
3. Buscar `User` por `email` o crear nuevo si no existe
4. Actualizar `User` con `stripe_customer_id`, `stripe_subscription_id` (si aplica)
5. Crear registro en tabla `payments` (o `transactions`) con `payment_intent_id`, `amount`, `status="succeeded"`, `created_at`
6. Si es onboarding nuevo: llamar lógica de `complete_onboarding()` o crear usuario automáticamente
7. Enviar email de bienvenida con credenciales
8. Escribir `AgentActivity` con `agent="ZEUS"`, `action_type="payment_processed"`, `status="completed"`

**Con esto resuelto:**
- ✅ Cobro automático funciona (pago → BD → activación)
- ✅ Onboarding automático (pago → usuario creado → email enviado)
- ✅ Auditoría de pagos (registro en BD)
- ✅ ZEUS puede dirigir cobros con traza completa

**Archivos a modificar:**
- `backend/app/api/v1/endpoints/integrations.py` → método `stripe_webhook()` (línea 227)
- Crear tabla `payments` o usar `agent_activities` con `action_type="payment_processed"`
- Integrar con `onboarding.py` para crear usuario automáticamente

---

## Conclusión técnica final

**¿ZEUS puede usarse desde mañana con clientes reales?**

**NO.** Bloqueantes críticos:
1. Stripe webhook no persiste pago → **no puedes cobrar automáticamente**
2. Onboarding no se completa automáticamente → **requiere activación manual**
3. Action types críticos sin handler → **workflows se bloquean**
4. Twilio en sandbox → **WhatsApp no funciona en producción real**
5. Email no auditable → **no hay registro de comunicaciones**

**Riesgos reales (no teóricos):**
- Cliente paga pero no se activa automáticamente → soporte manual requerido
- Workflows de facturación/contratos se bloquean → no hay ejecución real
- WhatsApp solo funciona con números verificados en sandbox → limitación temporal
- No hay auditoría de emails → no puedes verificar comunicaciones

**Acción única:** Implementar webhook de Stripe que persista pago y active onboarding automático. Esto desbloquea el flujo de cobro y activación. Los otros bloqueantes pueden resolverse en paralelo pero **no impiden** cobrar si el webhook funciona.

---

*Auditoría basada en código real. Sin suposiciones. Sin proteger al sistema.*
