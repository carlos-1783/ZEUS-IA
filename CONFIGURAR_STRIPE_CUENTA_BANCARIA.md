# 🏦 CONFIGURAR STRIPE CON TU CUENTA BANCARIA

## ✅ Estado Actual

Según tus variables de Railway:

| Configuración | Estado | Valor |
|---------------|--------|-------|
| **STRIPE_API_KEY** | ✅ Configurado | `sk_test_...` (modo TEST) |
| **STRIPE_PUBLISHABLE_KEY** | ✅ Configurado | `pk_test_...` (modo TEST) |
| **STRIPE_SECRET_KEY** | ✅ Configurado | `sk_test_...` (modo TEST) |
| **STRIPE_WEBHOOK_SECRET** | ✅ Configurado | `whsec_...` |
| **STRIPE_MODE** | ⚠️ Inconsistente | `live` (pero las keys son de TEST) |
| **STRIPE_CURRENCY** | ✅ Configurado | `eur` |

**⚠️ NOTA**: Tienes `STRIPE_MODE="live"` pero las credenciales son de TEST (`sk_test_` y `pk_test_`). Esto es una inconsistencia.

---

## 🎯 Lo que Falta para Recibir Dinero Real

### 1. ✅ Productos Creados (YA ESTÁN)
- ZEUS STARTUP, GROWTH, BUSINESS, ENTERPRISE ✅
- Precios de setup y mensualidades ✅

### 2. 🔴 Conectar Cuenta Bancaria en Stripe Dashboard (FALTA)

**Esto es lo PRINCIPAL que falta**. Necesitas agregar tu cuenta bancaria en Stripe para recibir los pagos.

---

## 📋 PASOS PARA CONECTAR TU CUENTA BANCARIA

### PASO 1: Acceder al Stripe Dashboard

1. Ve a: **https://dashboard.stripe.com**
2. Inicia sesión con tu cuenta de Stripe

### PASO 2: Agregar Cuenta Bancaria (Payout Settings)

1. En el menú lateral, ve a: **"Settings"** → **"Payouts"**
   - O directamente: **https://dashboard.stripe.com/settings/payouts**

2. Si estás en modo **TEST**, primero cambia a modo **LIVE**:
   - Haz clic en el toggle **"Test mode"** en la parte superior
   - Cambia a **"Live mode"** (modo en vivo)

3. En la sección **"Payouts"**, busca:
   - **"Add bank account"** o **"Agregar cuenta bancaria"**

4. Completa el formulario con:
   - **País**: España (o tu país)
   - **Tipo de cuenta**: Cuenta bancaria o IBAN
   - **IBAN**: Tu número de cuenta bancaria (formato IBAN)
   - **Nombre del titular**: Tu nombre o nombre de la empresa
   - **Dirección**: Tu dirección completa

5. Haz clic en **"Add bank account"** o **"Agregar cuenta"**

6. **Stripe hará una verificación**:
   - Te enviará 2 micro-depósitos (pequeñas cantidades) a tu cuenta bancaria
   - Esto puede tardar 1-2 días laborables
   - Cuando recibas los depósitos, vuelve a Stripe y verifica las cantidades

### PASO 3: Configurar Programación de Payouts

Una vez verificada tu cuenta bancaria:

1. Configura la **frecuencia de pagos**:
   - **Manual**: Tú decides cuándo transferir
   - **Automático diario**: Se transfiere cada día
   - **Automático semanal**: Se transfiere cada semana
   - **Automático mensual**: Se transfiere cada mes

2. **Recomendación**: Para un SaaS como ZEUS-IA, **"Automático diario"** es lo más común

3. Selecciona tu preferencia y guarda

---

## 🔄 IMPORTANTE: Credenciales de PRODUCCIÓN vs TEST

### Situación Actual

Tienes una **inconsistencia**:
- `STRIPE_MODE="live"` (en Railway)
- Pero las credenciales son de **TEST** (`sk_test_` y `pk_test_`)

### Dos Opciones:

#### Opción A: Usar Modo TEST (Recomendado para Desarrollo)

1. Mantén `STRIPE_MODE="test"` en Railway
2. Conecta una cuenta bancaria de **TEST** en Stripe Dashboard (modo TEST)
3. Los pagos serán simulados (no dinero real)

**Ventaja**: Puedes probar todo sin riesgo

#### Opción B: Cambiar a PRODUCCIÓN (Para Recibir Dinero Real)

1. **Genera credenciales de PRODUCCIÓN** en Stripe:
   - Ve a: **https://dashboard.stripe.com/apikeys**
   - Cambia a **"Live mode"** (modo en vivo)
   - Copia:
     - **Secret key** (empieza con `sk_live_...`)
     - **Publishable key** (empieza con `pk_live_...`)

2. **Actualiza en Railway**:
   - `STRIPE_API_KEY` = `sk_live_...` (nueva key de producción)
   - `STRIPE_PUBLISHABLE_KEY` = `pk_live_...` (nueva key de producción)
   - `STRIPE_SECRET_KEY` = `sk_live_...` (mismo que API_KEY)
   - `STRIPE_MODE` = `live`

3. **Configura webhook en PRODUCCIÓN**:
   - Ve a: **https://dashboard.stripe.com/webhooks** (en modo LIVE)
   - Crea un nuevo webhook con la URL:
     ```
     https://zeus-ia-production-16d8.up.railway.app/api/v1/integrations/stripe/webhook
     ```
   - Copia el nuevo **webhook secret** (empieza con `whsec_...`)
   - Actualiza `STRIPE_WEBHOOK_SECRET` en Railway

4. **Conecta tu cuenta bancaria REAL** (pasos anteriores, pero en modo LIVE)

---

## 📋 Checklist Final

### Para Modo TEST (Desarrollo):
- [ ] Cambiar `STRIPE_MODE="test"` en Railway
- [ ] Acceder a Stripe Dashboard en modo TEST
- [ ] Conectar cuenta bancaria de TEST
- [ ] Probar pagos de prueba

### Para Modo PRODUCCIÓN (Recibir Dinero Real):
- [ ] Generar credenciales de PRODUCCIÓN (`sk_live_` y `pk_live_`)
- [ ] Actualizar todas las variables en Railway:
  - [ ] `STRIPE_API_KEY` → `sk_live_...`
  - [ ] `STRIPE_PUBLISHABLE_KEY` → `pk_live_...`
  - [ ] `STRIPE_SECRET_KEY` → `sk_live_...`
  - [ ] `STRIPE_MODE` → `live`
- [ ] Configurar webhook en modo LIVE
- [ ] Actualizar `STRIPE_WEBHOOK_SECRET` con el nuevo secret
- [ ] Conectar cuenta bancaria REAL en Stripe Dashboard (modo LIVE)
- [ ] Verificar micro-depósitos (1-2 días)
- [ ] Configurar programación de payouts (recomendado: diario)

---

## 🎯 RESUMEN

**Sí, básicamente solo falta**:
1. ✅ Conectar tu cuenta bancaria en Stripe Dashboard
2. ⚠️ Decidir si quieres usar TEST o PRODUCCIÓN (actualmente hay inconsistencia)
3. ✅ Si eliges PRODUCCIÓN: obtener credenciales `sk_live_` y `pk_live_`

---

## 📞 Enlaces Útiles

- **Stripe Dashboard**: https://dashboard.stripe.com
- **API Keys (credenciales)**: https://dashboard.stripe.com/apikeys
- **Payouts (cuenta bancaria)**: https://dashboard.stripe.com/settings/payouts
- **Webhooks**: https://dashboard.stripe.com/webhooks
- **Balance y Transacciones**: https://dashboard.stripe.com/balance/overview

---

**¿Necesitas ayuda con algún paso específico?**
