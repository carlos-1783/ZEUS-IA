# 🚂 Variables de Entorno para Railway

## ⚠️ **IMPORTANTE: Configurar ANTES de desplegar**

Para que el backend funcione correctamente en Railway, necesitas configurar estas variables de entorno en el dashboard:

## 📋 **Variables Mínimas Requeridas**

### **1. Configuración Básica**
```bash
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=8000
```

### **2. Base de Datos (CRÍTICO)**
```bash
# Opción temporal para pruebas (SQLite):
DATABASE_URL=sqlite:///./zeus.db

# Opción producción (Neon - cuando lo configures):
# DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
```

### **3. Seguridad (CRÍTICO)**
```bash
SECRET_KEY=tu_clave_secreta_muy_segura_cambiar_en_produccion_2024
ALGORITHM=HS256
JWT_ISSUER=zeus-ia-backend
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_MINUTES=10080
```

### **4. CORS**
```bash
BACKEND_CORS_ORIGINS=["https://zeusia.app","https://www.zeusia.app","https://api.zeusia.app"]
```

### **5. URLs del Frontend**
```bash
FRONTEND_URL=https://zeusia.app
API_URL=https://api.zeusia.app
```

## 🎯 **Cómo Configurar en Railway**

1. Ve al dashboard de tu servicio en Railway
2. Click en **"Variables"** en el menú lateral
3. Click en **"+ New Variable"**
4. Agrega cada variable una por una
5. Click en **"Deploy"** para aplicar los cambios

## 🚀 **Orden Recomendado de Configuración**

### **Paso 1: Variables Mínimas (Para que inicie)**
```bash
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=sqlite:///./zeus.db
SECRET_KEY=tu_clave_secreta_muy_segura_2024
```

### **Paso 2: Verificar que Inicie**
- Espera a que el health check pase
- Verifica los logs

### **Paso 3: Agregar Variables Adicionales**
```bash
BACKEND_CORS_ORIGINS=["https://zeusia.app"]
FRONTEND_URL=https://zeusia.app
API_URL=https://api.zeusia.app
```

### **Paso 4: Migrar a PostgreSQL (Neon)**
- Crea base de datos en Neon
- Actualiza `DATABASE_URL` con la URL de Neon
- Railway reiniciará automáticamente

## 🔍 **Verificación Rápida**

Una vez configuradas las variables, verifica en los logs que veas:

```
🚀 Iniciando ZEUS-IA Backend...
✅ Aplicación importada correctamente
🌐 Iniciando servidor Gunicorn...
```

Si ves estos mensajes, el backend está funcionando correctamente.

## ⚡ **Solución Rápida**

Si quieres que el backend inicie YA, configura solo estas 3 variables:

```bash
ENVIRONMENT=production
DATABASE_URL=sqlite:///./zeus.db
SECRET_KEY=cambiar_esto_en_produccion_2024_muy_seguro
```

Y luego haz click en **"Redeploy"** en Railway.

## 📝 **Notas Importantes**

- ⚠️ SQLite es solo para pruebas, usa PostgreSQL (Neon) en producción
- ⚠️ Cambia el SECRET_KEY por uno generado aleatoriamente
- ⚠️ Configura BACKEND_CORS_ORIGINS con tu dominio real
- ✅ Railway reinicia automáticamente cuando cambias variables

---

**¿Ya configuraste estas variables en Railway?** Si no, ese es el motivo por el cual el health check falla.
