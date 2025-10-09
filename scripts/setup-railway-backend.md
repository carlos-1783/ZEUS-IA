# 🚂 Configuración de Backend en Railway

## Paso 1: Crear cuenta en Railway

1. **Ve a https://railway.app**
2. **Crea una cuenta gratuita** (permite hasta 500 horas/mes)
3. **Conecta tu cuenta de GitHub**

## Paso 2: Crear proyecto

1. **Haz clic en "New Project"**
2. **Selecciona "Deploy from GitHub repo"**
3. **Selecciona tu repositorio ZEUS-IA**
4. **Selecciona la rama `main`**

## Paso 3: Configurar servicio

1. **Railway detectará automáticamente el Dockerfile**
2. **Configura el servicio**:
   - **Nombre**: `zeus-backend`
   - **Puerto**: `8000`
   - **Comando de inicio**: `gunicorn app.main:app -c gunicorn.conf.py`

## Paso 4: Configurar variables de entorno

En el dashboard de Railway, ve a **Variables** y agrega:

```bash
# Configuración básica
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Base de datos (desde Neon)
DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require

# Redis (opcional, Railway puede proporcionar uno)
REDIS_URL=redis://default:password@redis.railway.internal:6379

# Seguridad
SECRET_KEY=tu_clave_secreta_muy_segura_aqui_cambiala
ALGORITHM=HS256
JWT_ISSUER=zeus-ia-backend
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# CORS
BACKEND_CORS_ORIGINS=["https://zeusia.app","https://www.zeusia.app","https://api.zeusia.app"]

# URLs del frontend
FRONTEND_URL=https://zeusia.app
API_URL=https://api.zeusia.app

# SSL/TLS
SSL_REDIRECT=true
FORCE_HTTPS=true

# Monitoreo
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=/app/logs/app.log
```

## Paso 5: Configurar dominio personalizado

1. **Ve a Settings > Domains**
2. **Agrega dominio**: `api.zeusia.app`
3. **Railway generará automáticamente el certificado SSL**

## Paso 6: Configurar Railway CLI (Opcional)

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Conectar al proyecto
railway connect

# Ver logs
railway logs

# Desplegar
railway up
```

## Paso 7: Verificar despliegue

1. **Ve a la URL generada por Railway**
2. **Verifica que responda**: `https://tu-proyecto.railway.app/health`
3. **Verifica la documentación**: `https://tu-proyecto.railway.app/docs`

## Configuración de Health Checks

Railway verificará automáticamente el endpoint `/health`:

```python
# Este endpoint ya está configurado en el backend
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

## Configuración de Logs

Railway captura automáticamente los logs. Puedes verlos en:

1. **Dashboard de Railway > Logs**
2. **CLI**: `railway logs`

## Configuración de Variables de Entorno Sensibles

Para variables sensibles como `SECRET_KEY`:

1. **Ve a Variables**
2. **Marca como "Secret"**
3. **Railway enmascarará el valor en los logs**

## Límites de la cuenta gratuita

- ✅ **500 horas de computación/mes**
- ✅ **1 GB de RAM**
- ✅ **1 vCPU**
- ✅ **Dominio personalizado**
- ✅ **SSL automático**
- ✅ **Logs centralizados**

## Próximos pasos

Una vez desplegado el backend:

1. ✅ **Verifica que el backend responda**
2. ✅ **Configura el dominio personalizado**
3. ✅ **Verifica los logs**
4. 🚀 **Procede al despliegue del frontend**

## Comandos útiles

```bash
# Ver estado del servicio
railway status

# Ver logs en tiempo real
railway logs --follow

# Conectar a la base de datos
railway connect

# Desplegar cambios
railway up

# Ver variables de entorno
railway variables
```

## Solución de problemas

### Backend no responde
1. **Verifica los logs**: `railway logs`
2. **Verifica las variables de entorno**
3. **Verifica la conexión a la base de datos**

### Error de migración
1. **Ejecuta migraciones manualmente**
2. **Verifica la URL de la base de datos**
3. **Verifica los permisos de la base de datos**

### Error de CORS
1. **Verifica BACKEND_CORS_ORIGINS**
2. **Asegúrate de incluir tu dominio frontend**
3. **Verifica que el frontend use HTTPS**
