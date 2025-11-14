# 🔗 Enlaces de Verificación - ZEUS IA

## 📊 Estado del Sistema

### Producción (Railway)
- **Dashboard**: https://zeus-ia-production-16d8.up.railway.app/dashboard
- **API Status**: https://zeus-ia-production-16d8.up.railway.app/api/v1/system/status
- **Agentes Status**: https://zeus-ia-production-16d8.up.railway.app/api/v1/agents/status
- **Autorizaciones Pendientes**: https://zeus-ia-production-16d8.up.railway.app/api/v1/system/pending-authorizations

### Local (Desarrollo)
- **Dashboard**: http://localhost:5173/dashboard
- **API Status**: http://localhost:8000/api/v1/system/status
- **Agentes Status**: http://localhost:8000/api/v1/agents/status
- **Autorizaciones Pendientes**: http://localhost:8000/api/v1/system/pending-authorizations

## 🔐 Tokens y Autorizaciones Pendientes

### Tokens Requeridos para Funcionalidad Completa

1. **GOOGLE_ADS_DEVELOPER_TOKEN** (PRIORIDAD ALTA)
   - **Estado**: Pendiente
   - **Requerido por**: PERSEO
   - **Para**: Crear y gestionar campañas de Google Ads
   - **Enlace**: https://ads.google.com/aw/apicenter
   - **⚠️ IMPORTANTE**: Si anteriormente solicitaste un token para otra aplicación (ej: web de marketing de afiliado), necesitas crear uno **NUEVO** específicamente para ZEUS IA
   - **Guía Completa**: Ver `docs/GUIA_GOOGLE_ADS_TOKEN.md` para instrucciones detalladas
   - **Instrucciones Rápidas**: 
     1. Ve a Google Ads API Center
     2. Completa la verificación del anunciante si está pendiente
     3. Solicita acceso como desarrollador
     4. **Proporciona "ZEUS IA" como nombre de aplicación** (NO uses el nombre de otra aplicación)
     5. Genera un Developer Token específico para ZEUS IA
     6. Añádelo como `GOOGLE_ADS_DEVELOPER_TOKEN` en Railway
   - **Cómo Verificar**: El token debe estar asociado a:
     - Nombre: "ZEUS IA"
     - Cuenta: 129-046-8001 Marketing Digital PER-SEO
     - Email: marketingdigitalper.seo@gmail.com

2. **GOOGLE_CREDENTIALS_JSON** (PRIORIDAD ALTA)
   - **Estado**: Pendiente/Verificar
   - **Requerido por**: PERSEO
   - **Para**: Integración completa con Google (Drive, Sheets, Calendar, Gmail)
   - **Enlace**: https://console.cloud.google.com/apis/credentials
   - **Instrucciones**:
     1. Ve a Google Cloud Console
     2. Crea un proyecto o selecciona uno existente
     3. Habilita las APIs necesarias (Drive, Sheets, Calendar, Gmail)
     4. Crea credenciales OAuth 2.0
     5. Descarga el JSON y añádelo como `GOOGLE_CREDENTIALS_JSON` en Railway

3. **LINKEDIN_ACCESS_TOKEN** (PRIORIDAD MEDIA)
   - **Estado**: Pendiente
   - **Requerido por**: PERSEO
   - **Para**: Publicación automática en LinkedIn
   - **Enlace**: https://www.linkedin.com/developers/apps

4. **TIKTOK_ACCESS_TOKEN** (PRIORIDAD MEDIA)
   - **Estado**: Pendiente
   - **Requerido por**: PERSEO
   - **Para**: Publicación automática en TikTok
   - **Enlace**: https://developers.tiktok.com/

## ✅ Tokens Configurados (Verificar)

- **OPENAI_API_KEY**: ✅ Configurado (requerido para todos los agentes)
- **STRIPE_SECRET_KEY**: ⚠️ Verificar en Railway
- **TWILIO_ACCOUNT_SID**: ⚠️ Verificar en Railway
- **SENDGRID_API_KEY**: ⚠️ Verificar en Railway

## 🔄 Comunicación Entre Agentes

### Estado Actual
- ✅ **ZEUS CORE** conectado a todos los agentes
- ✅ **PERSEO** puede comunicarse con RAFAEL y JUSTICIA
- ✅ **RAFAEL** puede comunicarse con JUSTICIA y PERSEO
- ✅ **JUSTICIA** puede comunicarse con RAFAEL y THALOS
- ✅ **AFRODITA** puede comunicarse con RAFAEL y JUSTICIA
- ✅ **THALOS** mantiene safeguards activos

### Cómo Funciona
Los agentes detectan automáticamente cuando necesitan ayuda de otros agentes basándose en palabras clave:

- **PERSEO** → RAFAEL: cuando detecta "factura", "iva", "impuesto", "fiscal"
- **PERSEO** → JUSTICIA: cuando detecta "legal", "contrato", "gdpr", "privacidad"
- **RAFAEL** → JUSTICIA: cuando detecta "legal", "contrato", "gdpr", "normativa"
- **RAFAEL** → PERSEO: cuando detecta "marketing", "campaña", "cliente"
- **JUSTICIA** → RAFAEL: cuando detecta "fiscal", "impuesto", "iva", "nómina"
- **JUSTICIA** → THALOS: cuando detecta "seguridad", "acceso", "credenciales"
- **AFRODITA** → RAFAEL: cuando detecta "fiscal", "nómina", "seguridad social"
- **AFRODITA** → JUSTICIA: cuando detecta "legal", "contrato", "despido", "gdpr"

## 📡 Endpoints de Comunicación

### Comunicación Directa Entre Agentes
```bash
POST /api/v1/chat/agents/communicate
{
  "from_agent": "PERSEO",
  "to_agent": "RAFAEL",
  "message": "Necesito información sobre IVA para una factura",
  "context": {}
}
```

### Coordinación Multi-Agente
```bash
POST /api/v1/chat/agents/coordinate
{
  "task_description": "Lanzar campaña de marketing con facturación",
  "required_agents": ["PERSEO", "RAFAEL", "JUSTICIA"],
  "context": {}
}
```

## 🧪 Pruebas de Comunicación

### Probar Comunicación PERSEO → RAFAEL
```bash
curl -X POST http://localhost:8000/api/v1/chat/perseo/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito crear una factura con IVA del 21%",
    "context": {}
  }'
```

Deberías ver en los logs:
```
📡 [PERSEO] Detecté necesidad de ayuda fiscal, consultando a RAFAEL...
📡 [ZEUS] PERSEO → RAFAEL: PERSEO necesita información fiscal...
✅ [ZEUS] RAFAEL respondió a PERSEO
```

## 📈 Métricas y Monitoreo

- **Actividades por Agente**: `/api/v1/activities/{AGENT}?days=7`
- **Métricas del Dashboard**: `/api/v1/metrics/dashboard`
- **Estado de Agentes**: `/api/v1/agents/status`
- **Outputs de Automatización**: `/api/v1/automation/outputs?agent={AGENT}`

## 🚀 Próximos Pasos

1. **Verificar tokens pendientes** usando `/api/v1/system/pending-authorizations`
2. **Configurar tokens faltantes** en Railway
3. **Probar comunicación entre agentes** con ejemplos reales
4. **Monitorear logs** para verificar que la comunicación funciona

## 📝 Notas Importantes

- Todos los agentes están conectados a ZEUS CORE
- La comunicación es automática cuando se detectan palabras clave
- Los agentes pueden comunicarse manualmente usando los endpoints `/agents/communicate` y `/agents/coordinate`
- El sistema está listo para recibir los tokens pendientes de Google Ads y otras plataformas

