# 🔍 VERIFICACIÓN DE VARIABLES DE ENTORNO EN VERCEL

## 📋 VARIABLES REQUERIDAS

### **Variables Críticas (OBLIGATORIAS):**
```env
VITE_API_URL=https://zeus-ia-production.up.railway.app
VITE_API_BASE_URL=https://zeus-ia-production.up.railway.app/api/v1
VITE_APP_NAME=ZEUS-IA
VITE_ENVIRONMENT=production
```

### **Variables Importantes:**
```env
VITE_APP_VERSION=1.0.0
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

## 🚀 PASOS PARA CONFIGURAR

1. **Ir a Vercel Dashboard**
2. **Seleccionar tu proyecto ZEUS-IA**
3. **Settings → Environment Variables**
4. **Agregar cada variable una por una**
5. **Asegurarse de que estén en "Production"**
6. **Redeployar el proyecto**

## ⚠️ PROBLEMAS COMUNES

- **"Cargando ZEUS IA..." infinito:** `VITE_API_URL` faltante o incorrecta
- **No se puede hacer login:** `VITE_API_BASE_URL` incorrecta
- **Errores de CORS:** `VITE_CORS_ORIGINS` incorrecta
- **Variables no se aplican:** No están marcadas para "Production"

## 🔧 SOLUCIÓN RÁPIDA

Si el problema persiste:
1. **Eliminar todas las variables de entorno**
2. **Agregar solo las variables críticas**
3. **Redeployar**
4. **Verificar que funcione**
5. **Agregar el resto de variables**
