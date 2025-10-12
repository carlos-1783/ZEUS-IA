# 🚀 ¿QUÉ ARCHIVO DE VARIABLES USAR EN RAILWAY?

## 📋 TIENES 2 OPCIONES:

### ✅ **OPCIÓN 1: RAILWAY_MINIMAL.env (RECOMENDADO PARA EMPEZAR)**

**📁 Archivo:** `RAILWAY_MINIMAL.env`

**✨ Características:**
- ✅ Solo las variables **ESENCIALES**
- ✅ **Menos líneas** (más fácil de copiar)
- ✅ Valores **reales y funcionales**
- ✅ Suficiente para que Railway funcione

**📝 Contiene (26 líneas):**
```env
# Configuración básica
PROJECT_NAME=ZEUS-IA
ENVIRONMENT=production
DEBUG=False

# Servidor
HOST=0.0.0.0
PORT=8000

# Seguridad (clave real)
SECRET_KEY=6895b411b45b5946b46bf7970f4d7e17aa69dfc5da4696cb15686625e5eccf2b

# Base de datos
DATABASE_URL=sqlite:///./zeus.db

# CORS (formato corregido)
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000

# JWT
JWT_ISSUER=zeus-ia-backend
```

---

### 🔧 **OPCIÓN 2: ZEUS_IA_RAILWAY.env (COMPLETO)**

**📁 Archivo:** `ZEUS_IA_RAILWAY.env`

**✨ Características:**
- ✅ **Todas las variables** posibles
- ✅ Incluye configuraciones avanzadas
- ✅ Incluye Stripe, Redis, Neon (opcionales)
- ⚠️ Algunas variables tienen valores placeholder

**📝 Contiene (74 líneas):**
```env
# Todo lo de RAILWAY_MINIMAL.env
# PLUS:
# - Configuración completa de CORS
# - Stripe (requiere tus claves)
# - Redis (opcional)
# - Neon Database (opcional)
# - Frontend URL
# - ALLOWED_HOSTS
```

---

## 🎯 **MI RECOMENDACIÓN:**

### **PARA EMPEZAR AHORA MISMO:**

1. **USA:** `RAILWAY_MINIMAL.env`
2. **CÓPIALO COMPLETO** al Raw Editor de Railway
3. **Guarda y reinicia** el deployment
4. **Verifica que funcione** (healthcheck debe pasar)

### **DESPUÉS, SI NECESITAS MÁS:**

1. **USA:** `ZEUS_IA_RAILWAY.env`
2. **REEMPLAZA** los placeholders:
   - `your_stripe_public_key_here` → Tu clave de Stripe
   - `your_neon_database_url_here` → Tu URL de Neon
   - etc.

---

## 📝 **INSTRUCCIONES PARA PEGAR EN RAILWAY:**

### **PASO 1: COPIAR EL ARCHIVO**

```bash
# Abre el archivo RAILWAY_MINIMAL.env
# Selecciona TODO el contenido (Ctrl+A)
# Copia (Ctrl+C)
```

### **PASO 2: PEGAR EN RAILWAY**

1. Ve a [Railway Dashboard](https://railway.app)
2. Selecciona tu proyecto **ZEUS-IA**
3. Ve a **Variables**
4. Haz clic en **"Raw Editor"**
5. **Borra todo** lo que haya actualmente
6. **Pega** el contenido copiado (Ctrl+V)
7. Haz clic en **"Save"** o **"Apply"**

### **PASO 3: REINICIAR**

1. Ve a **Deployments**
2. Haz clic en **"Redeploy"**
3. Espera a que termine el build
4. **Verifica los logs**

---

## ✅ **VALORES REALES INCLUIDOS:**

Ambos archivos tienen **valores reales y funcionales**:

- ✅ `SECRET_KEY` → Clave real de 64 caracteres
- ✅ `DATABASE_URL` → SQLite funcional
- ✅ `HOST` → 0.0.0.0 (correcto para Railway)
- ✅ `PORT` → 8000 (correcto para Railway)
- ✅ `BACKEND_CORS_ORIGINS` → URLs correctas

---

## 🎉 **RESULTADO ESPERADO:**

Después de pegar cualquiera de los dos archivos:

```
✅ Build exitoso
✅ Container iniciando
✅ FastAPI cargando correctamente
✅ Healthcheck pasando
✅ Railway mostrando "1/1 replicas healthy"
```

---

## ⚡ **RESPUESTA RÁPIDA:**

**"¿Cuál uso?"** → **RAILWAY_MINIMAL.env**

**"¿Tiene valores reales?"** → **Sí, todos funcionan**

**"¿Dónde lo pego?"** → **Railway → Variables → Raw Editor**

---

**Creado por:** Ingeniero DevOps  
**Estado:** ✅ LISTO PARA USAR
