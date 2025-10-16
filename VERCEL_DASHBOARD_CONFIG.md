# 🚀 CONFIGURACIÓN COMPLETA DE VERCEL DASHBOARD

## 🎯 PROBLEMA IDENTIFICADO

**Vercel no está sirviendo el HTML principal ni los archivos JavaScript. Solo sirve archivos CSS desde caché.**

## 🔧 SOLUCIÓN: CONFIGURAR VERCEL DASHBOARD

### 1. **Ir a Vercel Dashboard**
- URL: https://vercel.com/dashboard
- Seleccionar tu proyecto: `zeus-ia-gs9t`

### 2. **Settings → General**
Configurar:
- **Root Directory:** `frontend-vercel`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`
- **Framework Preset:** `Vite`

### 3. **Settings → Environment Variables**
Agregar TODAS estas variables:

```env
VITE_APP_NAME=ZEUS-IA
VITE_APP_VERSION=1.0.0
VITE_ENVIRONMENT=production
VITE_API_URL=https://zeus-ia-production.up.railway.app
VITE_API_BASE_URL=https://zeus-ia-production.up.railway.app/api/v1
VITE_DEBUG=false
VITE_LOG_LEVEL=info
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_ERROR_REPORTING=false
VITE_COMPANY_NAME=ZEUS-IA
VITE_SUPPORT_EMAIL=support@zeus-ia.com
VITE_DEFAULT_LANGUAGE=es
VITE_SUPPORTED_LANGUAGES=es,en
VITE_DEFAULT_THEME=light
VITE_ENABLE_DARK_MODE=true
VITE_CORS_ORIGINS=https://zeus-ia-gs9t.vercel.app
```

### 4. **Settings → Functions**
- **Node.js Version:** `18.x` o `20.x`

### 5. **Deployments → Redeploy**
- Hacer clic en "Redeploy" en el último deployment
- O hacer un nuevo commit para forzar redeploy

## ⚠️ PROBLEMAS COMUNES

### **Si sigue sin funcionar:**

1. **Eliminar proyecto de Vercel**
2. **Recrear proyecto desde GitHub**
3. **Configurar con las opciones de arriba**
4. **Redeployar**

### **Verificar que funcione:**
- ✅ HTML principal se carga (status 200)
- ✅ Archivos JS se cargan (status 200)
- ✅ Frontend se inicializa
- ✅ Login y registro funcionan

## 🚀 PASOS CRÍTICOS

1. **Root Directory:** DEBE ser `frontend-vercel`
2. **Framework Preset:** DEBE ser `Vite`
3. **Variables de entorno:** DEBEN estar en "Production"
4. **Redeploy:** DESPUÉS de configurar todo

## ⏰ TIEMPO ESTIMADO

**Después de configurar correctamente: 2-3 minutos para redeploy.**
