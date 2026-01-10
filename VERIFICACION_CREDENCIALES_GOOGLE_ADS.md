# 🔍 Verificación de Credenciales Google Ads

## 📋 Credenciales Necesarias para PERSEO

PERSEO necesita **4 credenciales obligatorias** para funcionar con Google Ads:

### ✅ 1. GOOGLE_ADS_DEVELOPER_TOKEN (OBLIGATORIO)
- **Estado**: ❌ FALTANTE (probablemente)
- **Dónde obtener**: https://ads.google.com/aw/apicenter
- **Qué es**: Token de desarrollador que Google aprueba manualmente
- **Tiempo de aprobación**: 1-5 días
- **Verificación**: El endpoint `/api/v1/system/pending-authorizations` muestra si falta

### ✅ 2. GOOGLE_ADS_CLIENT_ID (OBLIGATORIO)
- **Estado**: ✅ Ya creado en Google Cloud Console ("ZEUS IA - Google Ads C...")
- **Dónde obtener**: https://console.cloud.google.com/apis/credentials
- **Qué es**: ID de cliente OAuth2
- **Acción**: Copiar desde Google Cloud Console

### ✅ 3. GOOGLE_ADS_CLIENT_SECRET (OBLIGATORIO)
- **Estado**: ✅ Ya creado en Google Cloud Console (mismo lugar que Client ID)
- **Dónde obtener**: https://console.cloud.google.com/apis/credentials
- **Qué es**: Secreto de cliente OAuth2
- **Acción**: Copiar desde Google Cloud Console

### ✅ 4. GOOGLE_ADS_CUSTOMER_ID (OBLIGATORIO)
- **Estado**: ⚠️ Verificar en Railway
- **Valor**: `129-046-8001`
- **Dónde**: Tu cuenta de Google Ads

---

## 🔍 Cómo Verificar qué Falta

### Opción 1: Verificar desde el Sistema (Producción)

1. Ve a tu panel de admin (como superusuario):
   ```
   https://zeus-ia-production-16d8.up.railway.app/admin
   ```

2. O verifica directamente el endpoint:
   ```
   https://zeus-ia-production-16d8.up.railway.app/api/v1/system/pending-authorizations
   ```

3. Verás una lista de lo que falta

### Opción 2: Verificar en Railway

1. Ve a: https://railway.app
2. Selecciona tu proyecto ZEUS-IA
3. Selecciona el servicio **backend**
4. Ve a la pestaña **"Variables"**
5. Busca estas variables:

#### Variables que DEBES tener:
- [ ] `GOOGLE_ADS_DEVELOPER_TOKEN` = ¿Tiene un valor real o dice "pendiente"?
- [ ] `GOOGLE_ADS_CLIENT_ID` = ¿Tiene un valor real?
- [ ] `GOOGLE_ADS_CLIENT_SECRET` = ¿Tiene un valor real?
- [ ] `GOOGLE_ADS_CUSTOMER_ID` = `129-046-8001`

---

## 🎯 Problema Principal

Basándome en lo que veo en tu Google Cloud Console, **ya tienes las credenciales OAuth2** (Client ID y Secret), pero falta:

### 🚨 GOOGLE_ADS_DEVELOPER_TOKEN

Este es el que está bloqueando PERSEO. Este token:
- Se solicita desde Google Ads API Center
- Google lo aprueba manualmente (1-5 días)
- Sin él, PERSEO no puede acceder a la API aunque tengas las otras credenciales

---

## ✅ Próximos Pasos

### Paso 1: Obtener Client ID y Client Secret (Ya lo tienes)

1. Ve a: https://console.cloud.google.com/apis/credentials
2. Haz clic en la credencial **"ZEUS IA - Google Ads C..."**
3. Copia:
   - **ID de cliente** (Client ID)
   - **Secreto de cliente** (Client Secret)
4. **Verifica en Railway** que estos valores estén configurados correctamente

### Paso 2: Obtener Developer Token (Este es el crítico)

**Problema**: No puedes acceder a Google Ads API Center directamente.

**Solución Alternativa**:

1. **Verifica en Google Ads** si hay algún banner rojo de verificación pendiente
   - Si hay verificación pendiente, completa primero la verificación del anunciante

2. **Intenta acceder al API Center desde diferentes lugares**:
   - Menú lateral: Herramientas → Configuración → API Center
   - URL directa: https://ads.google.com/aw/apicenter
   - Desde Google Cloud Console (puede haber un enlace)

3. **Si definitivamente no puedes acceder al API Center**, contacta con Google Ads Support:
   - Explica que necesitas acceso al API Center para solicitar un Developer Token
   - Menciona que tu cuenta es administradora pero no ves la opción del API Center

### Paso 3: Configurar en Railway

Una vez tengas el **Developer Token**:

1. Ve a Railway → Variables
2. Añade o actualiza: `GOOGLE_ADS_DEVELOPER_TOKEN` = (tu token)
3. Verifica que también tengas:
   - `GOOGLE_ADS_CLIENT_ID` = (de Google Cloud Console)
   - `GOOGLE_ADS_CLIENT_SECRET` = (de Google Cloud Console)
   - `GOOGLE_ADS_CUSTOMER_ID` = `129-046-8001`

---

## 🆘 Si No Puedes Acceder al API Center

Si definitivamente no puedes acceder al API Center, hay dos opciones:

### Opción A: Contactar Soporte de Google Ads
- Explica que eres administrador pero no ves el API Center
- Pide ayuda para solicitar un Developer Token para tu aplicación

### Opción B: Verificar Permisos de Cuenta
- Asegúrate de que `marketingdigitalper.seo@gmail.com` tenga permisos de **Administrador** (no solo "Usuario")
- En Google Ads: Herramientas → Configuración → Acceso y seguridad
- Verifica que tu email tenga nivel **"Administrador"**

---

## 📞 Contacto con Google Ads Support

Si necesitas contactar a Google:

1. **Google Ads Support**: https://support.google.com/google-ads/answer/1728654
2. **Información a proporcionar**:
   - Nombre de aplicación: **ZEUS IA**
   - Cuenta: **129-046-8001**
   - Email: **marketingdigitalper.seo@gmail.com**
   - Problema: "No puedo acceder al API Center para solicitar Developer Token"

---

## ✅ Checklist Final

Antes de considerar PERSEO configurado:

- [ ] Client ID copiado desde Google Cloud Console
- [ ] Client Secret copiado desde Google Cloud Console
- [ ] Client ID configurado en Railway como `GOOGLE_ADS_CLIENT_ID`
- [ ] Client Secret configurado en Railway como `GOOGLE_ADS_CLIENT_SECRET`
- [ ] Developer Token obtenido desde Google Ads API Center
- [ ] Developer Token configurado en Railway como `GOOGLE_ADS_DEVELOPER_TOKEN`
- [ ] Customer ID configurado en Railway como `GOOGLE_ADS_CUSTOMER_ID` = `129-046-8001`
- [ ] Endpoint `/api/v1/system/pending-authorizations` ya NO muestra `GOOGLE_ADS_DEVELOPER_TOKEN`
- [ ] Endpoint `/api/v1/marketing/status` muestra `google_ads: configured: true`

---

**Última actualización**: 2025-01-13

