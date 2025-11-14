# 🔐 Guía Completa: Obtener Developer Token de Google Ads para ZEUS IA

## 🎯 Objetivo
Obtener un **Developer Token** de Google Ads que esté **específicamente asociado a ZEUS IA**, no a otra aplicación o web de marketing de afiliado.

---

## ⚠️ Situación Actual

Si anteriormente intentaste obtener un token para una **web de marketing de afiliado**, ese token **NO** pertenece a ZEUS IA. Necesitas crear uno nuevo específicamente para ZEUS IA.

---

## 🚨 PASO CRÍTICO: Completar Verificación del Anunciante

**ANTES** de solicitar el Developer Token, **DEBES** completar la verificación del anunciante.

### ¿Cómo saber si necesitas verificación?

Si ves un **banner rojo** en Google Ads que dice:
> "Cuenta en pausa - La fecha límite para la verificación ha pasado. Para reiniciar tus anuncios, completa la verificación de anunciante."

### Pasos para completar la verificación:

1. **Haz clic en el botón "Solucionarlo"** en el banner rojo
2. Sigue las instrucciones de Google para verificar tu identidad/negocio
3. **En la pregunta "¿Tu organización es una agencia de publicidad?"**:
   - **Selecciona "Sí"** porque ZEUS IA gestiona Google Ads para clientes
   - Esto es correcto ya que PERSEO automatiza la creación y gestión de campañas para tus clientes
   - Google puede pedirte documentación tanto de tu organización como de tus clientes
4. Proporciona la documentación requerida (puede incluir:
   - Identificación personal
   - Documentos del negocio (constitución de sociedad, etc.)
   - Información de contacto verificable
   - Dirección comercial
   - Documentos de clientes si Google los solicita)
5. Haz clic en "Guardar y continuar" y acepta los términos de verificación
6. Espera la aprobación de Google (puede tardar varios días)

### ⚠️ IMPORTANTE:
- **NO podrás obtener el Developer Token** hasta que la verificación esté completa
- La cuenta debe estar **activa y verificada** antes de solicitar acceso a la API
- Una vez verificada, el banner rojo desaparecerá y podrás proceder

---

## 📋 Paso 1: Verificar tu Cuenta de Google Ads

### 1.1 Acceder a Google Ads API Center
1. Ve a: **https://ads.google.com/aw/apicenter**
2. Inicia sesión con tu cuenta: `marketingdigitalper.seo@gmail.com`
3. Verifica que estás en la cuenta correcta: **129-046-8001 Marketing Digital PER-SEO**

### 1.2 Verificar que la Verificación del Anunciante está Completa
**IMPORTANTE**: 
- Si ves el banner rojo "Cuenta en pausa", **DEBES completar la verificación primero** (ver sección anterior)
- Solo después de que la verificación esté completa podrás solicitar el Developer Token
- Verifica que el estado de la cuenta sea "Activa" y sin banners de advertencia

---

## 🔑 Paso 2: Solicitar Developer Token para ZEUS IA

### 2.1 Información que DEBES proporcionar a Google

Cuando Google te pregunte sobre tu aplicación, proporciona esta información:

#### **Nombre de la Aplicación:**
```
ZEUS IA - Sistema de Automatización de Marketing con IA
```

#### **Descripción de la Aplicación:**
```
ZEUS IA es una plataforma de automatización empresarial que utiliza inteligencia artificial para gestionar campañas de marketing digital, incluyendo Google Ads. El sistema permite crear, optimizar y gestionar campañas publicitarias de forma automatizada mediante agentes de IA especializados (PERSEO - Growth Strategist).

La aplicación está diseñada para empresas que necesitan automatizar su marketing digital y gestionar múltiples campañas de forma eficiente.
```

#### **Tipo de Aplicación:**
```
Aplicación Web / API Backend
```

#### **URL de la Aplicación (Producción):**
```
https://zeus-ia-production-16d8.up.railway.app
```

#### **URL de la Aplicación (Desarrollo):**
```
http://localhost:8000
```

#### **Propósito del Uso:**
```
Gestión automatizada de campañas de Google Ads para clientes empresariales mediante plataforma SaaS. La aplicación permite:
- Crear campañas publicitarias automatizadas para múltiples clientes
- Optimizar campañas existentes mediante IA (agente PERSEO)
- Generar reportes de rendimiento automáticos
- Gestionar presupuestos y pujas de forma automatizada
- Proporcionar a los clientes una interfaz sencilla para automatizar su marketing sin conocimientos técnicos
```

#### **Tipo de Organización:**
```
Agencia de Publicidad / Plataforma SaaS de Automatización de Marketing
- Gestionamos Google Ads para múltiples clientes
- Automatizamos la creación y optimización de campañas mediante IA
- Los clientes utilizan nuestra plataforma para simplificar su marketing digital
```

#### **Casos de Uso Específicos:**
```
1. Creación automática de campañas basadas en objetivos de marketing
2. Optimización de palabras clave y pujas mediante análisis de IA
3. Generación de reportes de rendimiento y ROI
4. Gestión de múltiples cuentas de Google Ads desde una única plataforma
```

---

## ✅ Paso 3: Verificar que el Token Pertenece a ZEUS IA

### 3.1 Identificadores Únicos de ZEUS IA

Cuando recibas el Developer Token, verifica que esté asociado con:

- **Nombre de la aplicación**: "ZEUS IA" o similar
- **Cuenta de Google Ads**: 129-046-8001 Marketing Digital PER-SEO
- **Email asociado**: marketingdigitalper.seo@gmail.com

### 3.2 Cómo Verificar en Google Ads API Center

1. Ve a: **https://ads.google.com/aw/apicenter**
2. Busca la sección **"Developer Tokens"** o **"Tokens de Desarrollador"**
3. Verifica que el token muestre:
   - Nombre de la aplicación: **ZEUS IA**
   - Estado: **Activo** o **Pendiente de aprobación**
   - Fecha de creación: Reciente (no de cuando pediste el token para la web de afiliados)

---

## 🔄 Paso 4: Si Ya Tienes un Token para Otra Aplicación

### Opción A: Usar el Token Existente (NO RECOMENDADO)
**Problema**: El token está asociado a otra aplicación (web de marketing de afiliado), no a ZEUS IA.

**Riesgos**:
- Google puede rechazar solicitudes si detecta uso inconsistente
- No podrás identificar claramente qué solicitudes pertenecen a ZEUS IA
- Dificulta el debugging y soporte

### Opción B: Crear un Nuevo Token para ZEUS IA (RECOMENDADO)
**Ventajas**:
- Token específico para ZEUS IA
- Mejor trazabilidad y debugging
- Cumple con las políticas de Google Ads API
- Permite gestionar múltiples aplicaciones por separado

**Pasos**:
1. En Google Ads API Center, busca la opción **"Crear nuevo Developer Token"** o **"Request Access"**
2. Proporciona la información de ZEUS IA (ver Paso 2)
3. Espera la aprobación de Google (puede tardar varios días)

---

## 📝 Paso 5: Configurar el Token en ZEUS IA

Una vez que tengas el Developer Token aprobado:

### 5.1 En Railway (Producción)

1. Ve a tu proyecto en Railway: **https://railway.app**
2. Selecciona el servicio **backend**
3. Ve a la pestaña **"Variables"**
4. Busca o crea la variable: `GOOGLE_ADS_DEVELOPER_TOKEN`
5. Pega el token completo (sin espacios ni saltos de línea)
6. Guarda los cambios
7. El servicio se reiniciará automáticamente

### 5.2 En Local (.env)

1. Abre el archivo `.env` en la raíz del proyecto `backend/`
2. Añade o actualiza:
```env
GOOGLE_ADS_DEVELOPER_TOKEN=tu_token_aqui_sin_espacios
```
3. Reinicia el servidor backend

### 5.3 Verificar que Funciona

1. Ve a: **http://localhost:8000/api/v1/system/pending-authorizations** (local)
   o **https://zeus-ia-production-16d8.up.railway.app/api/v1/system/pending-authorizations** (producción)

2. Deberías ver que `GOOGLE_ADS_DEVELOPER_TOKEN` ya **NO** aparece en la lista de pendientes

3. Prueba crear una campaña de prueba:
```bash
curl -X POST http://localhost:8000/api/v1/marketing/google-ads/campaign \
  -H "Authorization: Bearer TU_TOKEN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Campaña de Prueba ZEUS",
    "budget": 100,
    "target_audience": "marketing digital"
  }'
```

---

## 🔍 Paso 6: Verificar Estado del Token

### Endpoint de Verificación

```bash
# Ver estado del sistema y tokens
GET /api/v1/system/status

# Ver autorizaciones pendientes
GET /api/v1/system/pending-authorizations

# Ver estado específico de marketing
GET /api/v1/marketing/status
```

### Respuesta Esperada

Si el token está correctamente configurado, deberías ver:

```json
{
  "marketing": {
    "google_ads": {
      "configured": true,
      "status": "active"
    }
  },
  "pending_tokens": [
    // GOOGLE_ADS_DEVELOPER_TOKEN NO debería aparecer aquí
  ]
}
```

---

## ⚠️ Problemas Comunes y Soluciones

### Problema 1: "Token no pertenece a esta aplicación"
**Solución**: Asegúrate de haber creado el token específicamente para ZEUS IA, no para otra aplicación.

### Problema 2: "Token pendiente de aprobación"
**Solución**: Google puede tardar varios días en aprobar el token. Mientras tanto, el sistema funcionará en modo limitado.

### Problema 3: "Cuenta en pausa - Verificación pendiente"
**Solución**: Completa primero la verificación del anunciante en Google Ads antes de solicitar el Developer Token.

### Problema 4: "Token anteriormente usado para otra aplicación"
**Solución**: Crea un nuevo token específicamente para ZEUS IA. No reutilices tokens de otras aplicaciones.

---

## 📞 Contacto con Google Ads Support

Si tienes problemas o necesitas aclaraciones:

1. **Google Ads API Support**: https://support.google.com/google-ads/answer/1728654
2. **Google Ads API Forum**: https://groups.google.com/g/adwords-api
3. **Documentación Oficial**: https://developers.google.com/google-ads/api/docs/start

**Información a proporcionar cuando contactes**:
- Nombre de la aplicación: **ZEUS IA**
- Cuenta de Google Ads: **129-046-8001**
- Email: **marketingdigitalper.seo@gmail.com**
- Propósito: **Automatización de campañas mediante IA**

---

## ✅ Checklist Final

Antes de considerar el proceso completo, verifica:

- [ ] Verificación del anunciante completada en Google Ads
- [ ] Developer Token solicitado específicamente para ZEUS IA
- [ ] Información proporcionada a Google incluye "ZEUS IA" como nombre de aplicación
- [ ] Token aprobado por Google (o en proceso de aprobación)
- [ ] Token configurado en Railway como `GOOGLE_ADS_DEVELOPER_TOKEN`
- [ ] Token configurado en `.env` local (si desarrollas localmente)
- [ ] Endpoint `/api/v1/system/pending-authorizations` ya NO muestra el token como pendiente
- [ ] Endpoint `/api/v1/marketing/status` muestra `google_ads: configured: true`

---

## 🎯 Resumen: Cómo Saber que el Token Pertenece a ZEUS IA

1. **Nombre de la aplicación**: Debe decir "ZEUS IA" o similar
2. **Fecha de creación**: Debe ser reciente (no de cuando pediste el token para afiliados)
3. **Cuenta asociada**: 129-046-8001 Marketing Digital PER-SEO
4. **Email**: marketingdigitalper.seo@gmail.com
5. **Verificación en código**: El endpoint `/api/v1/system/pending-authorizations` ya NO lo lista como pendiente

---

## 📚 Recursos Adicionales

- **Documentación de ZEUS IA**: `docs/ENLACES_VERIFICACION.md`
- **Configuración Completa**: `CONFIGURACION_COMPLETA.md`
- **Estado del Sistema**: `/api/v1/system/status`

---

**Última actualización**: 2025-01-13
**Mantenido por**: ZEUS IA DevOps Team

