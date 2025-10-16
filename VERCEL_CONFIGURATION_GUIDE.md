# 🚀 GUÍA DE CONFIGURACIÓN DE VERCEL PARA ZEUS-IA

## 📋 CONFIGURACIÓN REQUERIDA EN VERCEL DASHBOARD

### 1. **Variables de Entorno**
Ve a tu proyecto en Vercel Dashboard → Settings → Environment Variables y agrega:

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

### 2. **Configuración de Build**
- **Root Directory:** `frontend-vercel`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`
- **Framework Preset:** `Vite`

### 3. **Configuración de Dominio**
- **Production Domain:** `zeus-ia-gs9t.vercel.app`

## 🔧 PASOS PARA CONFIGURAR

1. **Ir a Vercel Dashboard**
2. **Seleccionar tu proyecto ZEUS-IA**
3. **Settings → Environment Variables**
4. **Agregar todas las variables de arriba**
5. **Settings → General**
6. **Configurar Root Directory: `frontend-vercel`**
7. **Redeployar el proyecto**

## ⚠️ PROBLEMAS COMUNES

- **"Cargando ZEUS IA..." infinito:** Variables de entorno faltantes
- **404 en rutas:** Configuración de SPA incorrecta
- **Errores de CORS:** VITE_CORS_ORIGINS mal configurado
- **No se puede hacer login:** VITE_API_URL incorrecto

## 🚀 SOLUCIÓN RÁPIDA

Si el problema persiste:
1. **Eliminar el proyecto de Vercel**
2. **Recrear el proyecto**
3. **Configurar con las variables de arriba**
4. **Redeployar**
