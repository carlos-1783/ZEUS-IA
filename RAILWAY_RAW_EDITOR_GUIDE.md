# 🚀 GUÍA PARA SUBIR VARIABLES DE ENTORNO EN RAILWAY

## 📋 INSTRUCCIONES PASO A PASO

### Paso 1: Acceder al Raw Editor de Railway
1. Ve a [Railway Dashboard](https://railway.app)
2. Selecciona tu proyecto **ZEUS-IA**
3. Ve a la pestaña **"Variables"**
4. Haz clic en **"Raw Editor"** (botón en la esquina superior derecha)

### Paso 2: Copiar y Pegar las Variables
Copia TODO el contenido del archivo `ZEUS_IA_RAILWAY.env` y pégalo en el Raw Editor:

```env
# ===============================================
# ZEUS-IA Backend - Variables de Entorno
# Configuración completa para Railway
# ===============================================

# ===== CONFIGURACIÓN BÁSICA =====
PROJECT_NAME=ZEUS-IA
VERSION=1.0.0
ENVIRONMENT=production
DEBUG=False

# ===== SERVIDOR =====
HOST=0.0.0.0
PORT=8000
RELOAD=False

# ===== SEGURIDAD JWT =====
SECRET_KEY=6895b411b45b5946b46bf7970f4d7e17aa69dfc5da4696cb15686625e5eccf2b
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
REFRESH_TOKEN_LENGTH=64
REFRESH_TOKEN_GRACE_PERIOD_DAYS=7

# ===== BASE DE DATOS =====
DATABASE_URL=sqlite:///./zeus.db

# ===== JWT CONFIGURACIÓN =====
JWT_AUDIENCE=["zeus-ia:auth","zeus-ia:access","zeus-ia:websocket"]
JWT_ISSUER=zeus-ia-backend
JWT_ACCESS_TOKEN_TYPE=access
JWT_WEBSOCKET_TOKEN_TYPE=websocket

# ===== CORS CONFIGURACIÓN =====
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000","http://127.0.0.1:5173","http://localhost:8000","http://127.0.0.1:8000"]
CORS_ALLOW_CREDENTIALS=True
CORS_ALLOW_METHODS=["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"]
CORS_ALLOW_HEADERS=["Accept","Accept-Encoding","Accept-Language","Authorization","Content-Type","Content-Length","DNT","Origin","User-Agent","X-Requested-With","X-CSRF-Token","Access-Control-Allow-Origin","Access-Control-Allow-Headers","Access-Control-Allow-Methods","Access-Control-Allow-Credentials","Cache-Control","Pragma","Expires","If-Modified-Since","If-None-Match"]
CORS_EXPOSE_HEADERS=["Content-Length","Content-Type","Content-Disposition","Authorization"]

# ===== ARCHIVOS ESTÁTICOS =====
STATIC_URL=/static
STATIC_DIR=static

# ===== LOGGING =====
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# ===== SEGURIDAD =====
SECURE_HSTS_SECONDS=31536000
TRUSTED_HOSTS=*

# ===== PAYMENTS (Stripe) =====
STRIPE_PUBLIC_KEY=your_stripe_public_key_here
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here

# ===== FRONTEND URL =====
FRONTEND_URL=http://localhost:5173
ALLOWED_HOSTS=localhost,127.0.0.1,zeusia.app,api.zeusia.app

# ===== REDIS (Opcional) =====
REDIS_URL=redis://localhost:6379

# ===== NEON DATABASE (Opcional para PostgreSQL) =====
NEON_DATABASE_URL=your_neon_database_url_here
NEON_POOLER_URL=your_neon_pooler_url_here
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# ===== RAILWAY ESPECÍFICO =====
RAILWAY_TOKEN=your_railway_token_here
RAILWAY_PROJECT_ID=your_railway_project_id_here
```

### Paso 3: Guardar las Variables
1. Haz clic en **"Save"** o **"Apply"**
2. Espera a que Railway procese las variables
3. Verifica que todas las variables aparezcan en la lista

### Paso 4: Reiniciar el Servicio
1. Ve a la pestaña **"Deployments"**
2. Haz clic en **"Redeploy"** o **"Restart"**
3. Espera a que termine el build y deployment

### Paso 5: Verificar el Healthcheck
1. Ve a la pestaña **"Logs"**
2. Deberías ver:
```
=== ZEUS-IA FastAPI Backend Starting ===
Host: 0.0.0.0, Port: 8000
✅ FastAPI app loaded successfully
🚀 Starting Uvicorn server...
INFO: Started server process [1]
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

3. El servicio debería mostrar **"1/1 replicas healthy"**

## 🎯 VARIABLES CRÍTICAS PARA EL HEALTHCHECK

Las variables más importantes para que funcione el healthcheck son:

- `SECRET_KEY` - Clave secreta JWT
- `DATABASE_URL` - URL de la base de datos
- `DEBUG=False` - Modo producción
- `HOST=0.0.0.0` - Host del servidor
- `PORT=8000` - Puerto del servidor
- `ENVIRONMENT=production` - Entorno de producción

## ✅ RESULTADO ESPERADO

Después de seguir estos pasos:
- ✅ Railway mostrará "1/1 replicas healthy"
- ✅ El endpoint `/health` responderá con código 200
- ✅ El servicio estará completamente funcional

## 🚨 Si Sigue Fallando

Si después de configurar las variables el healthcheck sigue fallando:
1. Verifica que todas las variables estén configuradas correctamente
2. Revisa los logs en Railway → Logs
3. Confirma que no hay errores de importación
4. Reinicia el deployment después de agregar las variables
