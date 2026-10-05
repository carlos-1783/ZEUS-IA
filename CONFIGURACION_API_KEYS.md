# 🔑 ZEUS-IA - Configuración de API Keys

## 📋 RESUMEN

Para que ZEUS-IA funcione al 100%, necesitas configurar las siguientes API keys en Railway:

| Servicio | Estado | Prioridad | Tiempo Setup |
|----------|--------|-----------|--------------|
| **OpenAI** | ⚠️ Requerido | 🔴 CRÍTICA | 5 min |
| **Twilio (WhatsApp)** | ⚠️ Requerido | 🔴 ALTA | 15 min |
| **SendGrid (Email)** | ⚠️ Requerido | 🔴 ALTA | 10 min |
| **Stripe** | ⚠️ Requerido | 🟡 MEDIA | 10 min |
| **Hacienda (AEAT)** | ⚠️ Opcional | 🟢 BAJA | 30 min |

---

## 1️⃣ OPENAI (CRÍTICO - Sin esto los agentes no funcionan)

### **¿Qué hace?**
- Los agentes IA (ZEUS, PERSEO, RAFAEL, etc.) usan GPT para responder
- **Sin OpenAI, ZEUS NO FUNCIONA**

### **Cómo conseguir la API Key:**

1. **Ve a:** https://platform.openai.com/api-keys
2. **Login** con tu cuenta OpenAI (o créala)
3. **Click en:** "Create new secret key"
4. **Copia** la key (empieza con `sk-proj-...`)
5. **Guárdala** en un lugar seguro (solo se muestra una vez)

### **Configurar en Railway:**

```bash
OPENAI_API_KEY=sk-proj-TU_API_KEY_AQUI
OPENAI_MODEL=gpt-4  # O gpt-3.5-turbo (más barato)
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.3
```

### **Costo estimado:**
- **GPT-3.5-turbo:** ~$0.002 por 1,000 tokens (~$10-20/mes uso moderado)
- **GPT-4:** ~$0.03 por 1,000 tokens (~$100-200/mes uso moderado)

---

## 2️⃣ TWILIO (WhatsApp)

### **¿Qué hace?**
- Permite que ZEUS responda automáticamente a mensajes de WhatsApp
- Clientes escriben a tu número → ZEUS responde al instante

### **Cómo conseguir las credenciales:**

1. **Ve a:** https://www.twilio.com/try-twilio
2. **Regístrate** (gratis, te dan $15 de crédito)
3. **Verifica** tu número de teléfono
4. **Ve a Console:** https://console.twilio.com
5. **Copia:**
   - **Account SID** (AC...)
   - **Auth Token** (haz click en "Show")
6. **Para WhatsApp:**
   - Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
   - Activa el **WhatsApp Sandbox**
   - Tu número será: `whatsapp:+14155238886` (sandbox)
   - Para producción necesitas **WhatsApp Business** (requiere aprobación de Facebook)

### **Configurar en Railway:**

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=tu_auth_token_aqui
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886  # Sandbox
```

### **Webhook de Twilio:**

Configura en Twilio Sandbox:
```
https://zeus-ia-production-16d8.up.railway.app/api/v1/integrations/whatsapp/webhook
```

**Verificacion de firma (obligatoria):** el backend valida `X-Twilio-Signature` con `TWILIO_AUTH_TOKEN`
(sin token responde 503; firma ausente o invalida, 403). La URL firmada se reconstruye con
`PUBLIC_BASE_URL` si esta definida (ej. `https://zeus-ia-production-16d8.up.railway.app`), si no con
`X-Forwarded-Proto`/`X-Forwarded-Host`. Debe coincidir EXACTAMENTE con la URL puesta en Twilio.
Tambien aplica a `/api/v1/webhooks/twilio`.

### **Webhook de email entrante (SendGrid Inbound Parse):**

Variable nueva (sin valor en el repo): `EMAIL_INBOUND_WEBHOOK_SECRET`. En SendGrid, Destination URL:
```
https://<backend>/api/v1/integrations/email/webhook?secret=<EMAIL_INBOUND_WEBHOOK_SECRET>
```
(tambien se acepta la cabecera `X-Inbound-Secret`). Sin variable configurada responde 503; secreto incorrecto, 403.
Variables nuevas: `PUBLIC_BASE_URL` (opcional), `EMAIL_INBOUND_WEBHOOK_SECRET`.

### **Costo:**
- **Sandbox:** Gratis (para pruebas)
- **Producción:** ~$0.005 por mensaje (~$10-30/mes uso moderado)

---

## 3️⃣ SENDGRID (Email)

### **¿Qué hace?**
- ZEUS responde automáticamente a emails de clientes
- Envía facturas, recordatorios, notificaciones

### **Cómo conseguir la API Key:**

1. **Ve a:** https://signup.sendgrid.com
2. **Regístrate** (gratis, 100 emails/día)
3. **Verifica** tu email
4. **Ve a:** https://app.sendgrid.com/settings/api_keys
5. **Click en:** "Create API Key"
6. **Permisos:** "Full Access" (o solo "Mail Send")
7. **Copia** la key (empieza con `SG.`)

### **Configurar dominio (opcional pero recomendado):**

1. **Ve a:** https://app.sendgrid.com/settings/sender_auth/senders
2. **Verifica** tu dominio (zeus-ia.com o el que uses)
3. **Agrega registros DNS** que SendGrid te indica

### **Configurar en Railway:**

```bash
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=noreply@tu-dominio.com
SENDGRID_FROM_NAME=ZEUS-IA
```

### **Webhook para recibir emails (Inbound Parse):**

1. **Ve a:** https://app.sendgrid.com/settings/parse
2. **Configura:**
   - **Hostname:** `inbox.tu-dominio.com`
   - **URL:** `https://zeus-ia-production-16d8.up.railway.app/api/v1/integrations/email/webhook`
3. **Agrega registro MX** en tu DNS

### **Costo:**
- **Free:** 100 emails/día (suficiente para empezar)
- **Essentials:** $19.95/mes - 50,000 emails/mes

---

## 4️⃣ STRIPE (Pagos)

### **¿Qué hace?**
- Procesa pagos de clientes
- Gestiona suscripciones
- Pagos automáticos integrados con RAFAEL (facturación)

### **Cómo conseguir las credenciales:**

1. **Ve a:** https://dashboard.stripe.com/register
2. **Regístrate** (gratis)
3. **Ve a:** https://dashboard.stripe.com/test/apikeys
4. **Copia:**
   - **Publishable key** (pk_test_...)
   - **Secret key** (sk_test_...)
5. **Para webhooks:**
   - Ve a: https://dashboard.stripe.com/test/webhooks
   - **Add endpoint:** `https://zeus-ia-production-16d8.up.railway.app/api/v1/integrations/stripe/webhook`
   - **Selecciona eventos:** `payment_intent.succeeded`, `payment_intent.payment_failed`
   - **Copia Signing secret** (whsec_...)

### **Configurar en Railway:**

```bash
STRIPE_API_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_CURRENCY=eur
STRIPE_MODE=test
```

### **Pasar a producción:**

1. **Verifica** tu negocio en Stripe (requiere datos fiscales)
2. **Cambia** a production keys (sk_live_...)
3. **Configura** nuevo webhook con production URL
4. **Actualiza** la variable `STRIPE_MODE=live` en Railway
5. **Verifica** con `GET /api/v1/integrations/stripe/status` que `detected_mode` y `requested_mode` sean `live`

### **Costo:**
- **Sin cuota mensual**
- **Comisión:** 1.4% + €0.25 por transacción en Europa

---

## 5️⃣ HACIENDA (AEAT) - Opcional

### **¿Qué hace?**
- Envía facturas al SII (Suministro Inmediato de Información)
- Presenta modelos fiscales (303, 390, etc.)
- **NOTA:** Requiere certificado digital de empresa

### **Requisitos:**

1. **Certificado Digital:**
   - Obtenerlo de FNMT: https://www.sede.fnmt.gob.es
   - O certificado de empresa emitido por autoridad certificadora
2. **NIF de la empresa**
3. **Contraseña del certificado**

### **Configurar en Railway:**

```bash
AEAT_NIF=B12345678
AEAT_PASSWORD=tu_password_certificado
AEAT_ENVIRONMENT=test  # o production
AEAT_CERTIFICATE_PATH=/app/certs/certificado.pfx
```

### **Modo TEST:**
- ZEUS puede calcular modelos sin enviarlos a AEAT
- Útil para validar antes de enviar

---

## 🚀 CONFIGURACIÓN EN RAILWAY

### **PASO 1: Ir a variables de entorno**

1. **Ve a:** https://railway.app
2. **Proyecto:** zeus-ia-production-16d8
3. **Click en:** "Variables"

### **PASO 2: Agregar variables (una por una)**

```bash
# OPENAI (CRÍTICO)
OPENAI_API_KEY=sk-proj-...

# TWILIO (WhatsApp)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# SENDGRID (Email)
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=noreply@zeus-ia.com
SENDGRID_FROM_NAME=ZEUS-IA

# STRIPE (Pagos)
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=eur

# HACIENDA (Opcional)
AEAT_NIF=B12345678
AEAT_PASSWORD=...
AEAT_ENVIRONMENT=test
```

### **PASO 3: Guardar y redesplegar**

Railway se redesplegará automáticamente al guardar las variables.

---

## 🔥 VERIFICACIÓN

### **Una vez configurado, verifica:**

```bash
# 1. Health check
curl https://zeus-ia-production-16d8.up.railway.app/api/v1/health

# 2. Estado de integraciones
curl https://zeus-ia-production-16d8.up.railway.app/api/v1/integrations/status
```

**Deberías ver:**
```json
{
  "whatsapp": {
    "configured": true,
    "provider": "Twilio"
  },
  "email": {
    "configured": true,
    "provider": "SendGrid"
  },
  "stripe": {
    "configured": true,
    "mode": "test"
  }
}
```

---

## 💡 ORDEN RECOMENDADO DE CONFIGURACIÓN

### **Día 1 - Esencial:**
1. ✅ **OPENAI** (sin esto nada funciona)
2. ✅ **Database** (ya configurado en Railway)

### **Día 2 - Comunicaciones:**
3. ✅ **SendGrid** (Email automation)
4. ✅ **Twilio** (WhatsApp automation)

### **Día 3 - Pagos:**
5. ✅ **Stripe** (modo test primero)

### **Día 4 - Fiscal:**
6. ✅ **Hacienda** (cuando tengas certificado)

---

## 🎯 LINKS ÚTILES

| Servicio | Dashboard | Documentación |
|----------|-----------|---------------|
| OpenAI | https://platform.openai.com | https://platform.openai.com/docs |
| Twilio | https://console.twilio.com | https://www.twilio.com/docs/whatsapp |
| SendGrid | https://app.sendgrid.com | https://docs.sendgrid.com |
| Stripe | https://dashboard.stripe.com | https://stripe.com/docs |
| AEAT | https://www.agenciatributaria.es | https://www.aeat.es/es/sii |

---

## ⚠️ IMPORTANTE

**NO compartas las API keys:**
- ❌ NO las subas a GitHub
- ❌ NO las pongas en el código
- ✅ Solo en variables de entorno de Railway
- ✅ Usa `.env` solo localmente (y está en `.gitignore`)

**Rotar keys si se filtran:**
- Twilio: https://console.twilio.com/us1/account/keys-credentials/api-keys
- SendGrid: https://app.sendgrid.com/settings/api_keys
- Stripe: https://dashboard.stripe.com/test/apikeys
- OpenAI: https://platform.openai.com/api-keys

---

## 📞 SOPORTE

Si tienes problemas configurando:
1. Verifica que las keys están bien copiadas (sin espacios extra)
2. Chequea `/api/v1/integrations/status` para ver qué falta
3. Revisa logs de Railway para errores específicos

**Una vez todo configurado, ZEUS estará 100% operativo.** ⚡

