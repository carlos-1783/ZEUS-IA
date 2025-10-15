# 🌐 VARIABLES DE ENTORNO PARA VERCEL

## 📋 VARIABLES NECESARIAS PARA EL FRONTEND

### **🔧 VARIABLES BÁSICAS:**

```env
# ===== CONFIGURACIÓN BÁSICA =====
VITE_APP_NAME=ZEUS-IA
VITE_APP_VERSION=1.0.0
VITE_ENVIRONMENT=production

# ===== API BACKEND (RAILWAY) =====
VITE_API_URL=https://tu-railway-backend.railway.app
VITE_API_BASE_URL=https://tu-railway-backend.railway.app/api/v1

# ===== CORS Y SEGURIDAD =====
VITE_CORS_ORIGINS=https://tu-vercel-frontend.vercel.app,https://zeus-ia.vercel.app

# ===== CONFIGURACIÓN DE DESARROLLO =====
VITE_DEBUG=false
VITE_LOG_LEVEL=info

# ===== FEATURES =====
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_ERROR_REPORTING=true
```

---

## 🎯 VARIABLES ESPECÍFICAS PARA ZEUS-IA

### **📊 VARIABLES DE NEGOCIO:**

```env
# ===== CONFIGURACIÓN DE EMPRESA =====
VITE_COMPANY_NAME=ZEUS-IA
VITE_COMPANY_LOGO=https://tu-vercel-frontend.vercel.app/logo.png
VITE_SUPPORT_EMAIL=support@zeus-ia.com

# ===== CONFIGURACIÓN DE PAGOS =====
VITE_STRIPE_PUBLIC_KEY=pk_test_tu_stripe_public_key_aqui
VITE_CURRENCY=USD
VITE_CURRENCY_SYMBOL=$

# ===== CONFIGURACIÓN DE IDIOMA =====
VITE_DEFAULT_LANGUAGE=es
VITE_SUPPORTED_LANGUAGES=es,en

# ===== CONFIGURACIÓN DE TEMA =====
VITE_DEFAULT_THEME=light
VITE_ENABLE_DARK_MODE=true
```

---

## 🔗 VARIABLES DE INTEGRACIÓN

### **🗄️ BASE DE DATOS (SI EL FRONTEND NECESITA ACCESO DIRECTO):**

```env
# ===== NEON DATABASE (OPCIONAL) =====
VITE_NEON_URL=postgresql://neondb_owner:password@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
VITE_DB_POOL_SIZE=5
```

### **📧 SERVICIOS EXTERNOS:**

```env
# ===== EMAIL SERVICE =====
VITE_EMAIL_SERVICE_URL=https://api.emailservice.com
VITE_EMAIL_API_KEY=tu_email_api_key

# ===== ANALYTICS =====
VITE_GOOGLE_ANALYTICS_ID=GA-XXXXXXXXX
VITE_MIXPANEL_TOKEN=tu_mixpanel_token

# ===== MONITORING =====
VITE_SENTRY_DSN=https://tu_sentry_dsn@sentry.io/project_id
```

---

## 🚀 CONFIGURACIÓN EN VERCEL

### **PASO 1: Ir a Vercel Dashboard**
1. Ve a: https://vercel.com
2. Selecciona tu proyecto ZEUS-IA
3. Ve a: **Settings** → **Environment Variables**

### **PASO 2: Agregar Variables**
1. Haz clic en **"Add New"**
2. Agrega cada variable una por una
3. Marca **"Production"**, **"Preview"**, y **"Development"**

### **PASO 3: Variables Críticas (MÍNIMAS)**
```env
VITE_APP_NAME=ZEUS-IA
VITE_API_URL=https://tu-railway-backend.railway.app
VITE_ENVIRONMENT=production
```

---

## ⚠️ IMPORTANTE

### **🔒 SEGURIDAD:**
- **NUNCA** pongas claves secretas en variables `VITE_`
- Las variables `VITE_` son **públicas** en el frontend
- Para secretos, usa variables del backend (Railway)

### **🔄 REBUILD:**
- Después de agregar variables, haz **"Redeploy"** en Vercel
- Las variables `VITE_` se compilan en el build

---

## 📝 PRÓXIMO PASO

**Necesito la URL de tu backend de Railway para completar las variables.**

**¿Puedes ir a Railway y copiar la URL del backend?** Debería verse así:
```
https://zeus-ia-production-xxxxx.up.railway.app
```

Una vez que tengas esa URL, actualizaré las variables con la URL correcta.
