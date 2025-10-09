# 🚀 ZEUS-IA - Guía de Despliegue en la Nube

Esta guía te llevará paso a paso para desplegar ZEUS-IA en producción usando servicios cloud modernos.

## 📋 **Requisitos Previos**

- Cuenta en [Railway](https://railway.app) (Backend)
- Cuenta en [Vercel](https://vercel.com) (Frontend)
- Cuenta en [Neon](https://neon.tech) (Base de datos)
- Dominio `zeusia.app` (opcional, pero recomendado)
- GitHub Actions habilitado

## 🏗️ **Arquitectura de Producción**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (Vercel)      │◄──►│   (Railway)     │◄──►│   (Neon)        │
│   zeusia.app    │    │   api.zeusia.app│    │   PostgreSQL    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Monitoring    │
                    │   & Analytics   │
                    └─────────────────┘
```

## 🔧 **Paso 1: Configurar Base de Datos (Neon)**

### 1.1 Crear Base de Datos
```bash
# 1. Ve a https://neon.tech
# 2. Crea una nueva cuenta
# 3. Crea un nuevo proyecto llamado "zeus-ia-prod"
# 4. Selecciona la región más cercana a tus usuarios
```

### 1.2 Configurar Variables de Entorno
```bash
# Copia la URL de conexión de Neon
# Formato: postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
```

### 1.3 Ejecutar Migraciones
```bash
# Instalar Alembic si no está instalado
pip install alembic

# Ejecutar migraciones
cd backend
alembic upgrade head
```

## 🚂 **Paso 2: Desplegar Backend (Railway)**

### 2.1 Configurar Railway
```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login en Railway
railway login

# 3. Crear nuevo proyecto
railway init zeus-ia-backend

# 4. Conectar repositorio GitHub
railway connect
```

### 2.2 Configurar Variables de Entorno en Railway
```bash
# Variables requeridas:
DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
SECRET_KEY=tu_clave_secreta_muy_segura_aqui
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=["https://zeusia.app","https://www.zeusia.app"]
```

### 2.3 Desplegar Backend
```bash
# Desde el directorio del proyecto
railway up
```

## 🌐 **Paso 3: Desplegar Frontend (Vercel)**

### 3.1 Configurar Vercel
```bash
# 1. Instalar Vercel CLI
npm install -g vercel

# 2. Login en Vercel
vercel login

# 3. Crear proyecto
cd frontend
vercel
```

### 3.2 Configurar Variables de Entorno en Vercel
```bash
# Variables requeridas:
VITE_API_URL=https://api.zeusia.app
VITE_WS_URL=wss://api.zeusia.app
VITE_ENVIRONMENT=production
```

### 3.3 Desplegar Frontend
```bash
# Despliegue en producción
vercel --prod
```

## 🔐 **Paso 4: Configurar Dominio Personalizado**

### 4.1 Configurar DNS
```bash
# Configurar registros DNS:
# A record: @ -> IP del servidor Railway
# CNAME: www -> zeusia.app
# CNAME: api -> railway.app
```

### 4.2 Configurar SSL
```bash
# Railway maneja SSL automáticamente
# Vercel maneja SSL automáticamente
# Solo necesitas configurar el dominio en cada plataforma
```

## 🔄 **Paso 5: Configurar CI/CD (GitHub Actions)**

### 5.1 Configurar Secrets en GitHub
```bash
# Ve a tu repositorio en GitHub > Settings > Secrets and variables > Actions
# Agrega los siguientes secrets:

RAILWAY_TOKEN=tu_token_de_railway
VERCEL_TOKEN=tu_token_de_vercel
VERCEL_ORG_ID=tu_org_id_de_vercel
VERCEL_PROJECT_ID=tu_project_id_de_vercel
NEON_DATABASE_URL=tu_url_de_neon
```

### 5.2 Configurar Workflow
```bash
# El archivo .github/workflows/deploy.yml ya está configurado
# Solo necesitas hacer push a la rama main para activar el despliegue
```

## 📊 **Paso 6: Configurar Monitoreo**

### 6.1 Uptime Monitoring
```bash
# 1. Ve a https://uptimerobot.com
# 2. Crea una cuenta gratuita
# 3. Agrega monitores para:
#    - https://zeusia.app
#    - https://api.zeusia.app/health
```

### 6.2 Error Tracking
```bash
# 1. Ve a https://sentry.io
# 2. Crea una cuenta gratuita
# 3. Configura Sentry en el backend
```

### 6.3 Analytics
```bash
# 1. Ve a https://analytics.google.com
# 2. Crea una propiedad para zeusia.app
# 3. Agrega el tracking code al frontend
```

## 🧪 **Paso 7: Validar Despliegue**

### 7.1 Ejecutar Script de Validación
```bash
# Ejecutar validación completa
.\scripts\validate-production.ps1 -FullTest

# Validación básica
.\scripts\validate-production.ps1
```

### 7.2 Tests Manuales
```bash
# 1. Verificar frontend: https://zeusia.app
# 2. Verificar API: https://api.zeusia.app/health
# 3. Probar registro de usuario
# 4. Probar login de usuario
# 5. Verificar PWA en móvil
```

## 🔧 **Comandos Útiles**

### Railway
```bash
# Ver logs
railway logs

# Conectar a la base de datos
railway connect

# Desplegar
railway up
```

### Vercel
```bash
# Ver logs
vercel logs

# Desplegar
vercel --prod

# Ver dominio
vercel domains ls
```

### Neon
```bash
# Conectar con psql
psql "postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require"

# Ver conexiones activas
SELECT * FROM pg_stat_activity;
```

## 🚨 **Solución de Problemas**

### Backend no responde
```bash
# 1. Verificar logs en Railway
railway logs

# 2. Verificar variables de entorno
railway variables

# 3. Verificar base de datos
railway connect
```

### Frontend no carga
```bash
# 1. Verificar logs en Vercel
vercel logs

# 2. Verificar build
vercel build

# 3. Verificar variables de entorno
vercel env ls
```

### Base de datos no conecta
```bash
# 1. Verificar URL de conexión
# 2. Verificar permisos de usuario
# 3. Verificar configuración SSL
```

## 📈 **Optimizaciones de Producción**

### Backend
- ✅ Configurar rate limiting
- ✅ Habilitar compresión gzip
- ✅ Configurar cache headers
- ✅ Optimizar queries de base de datos

### Frontend
- ✅ Habilitar Service Worker
- ✅ Configurar cache strategies
- ✅ Optimizar imágenes
- ✅ Habilitar lazy loading

### Base de Datos
- ✅ Configurar índices
- ✅ Habilitar connection pooling
- ✅ Configurar backups automáticos
- ✅ Monitorear performance

## 🎯 **URLs Finales**

Después del despliegue exitoso, tendrás acceso a:

- **Frontend**: https://zeusia.app
- **API**: https://api.zeusia.app
- **Health Check**: https://api.zeusia.app/health
- **Admin Panel**: https://zeusia.app/admin
- **API Docs**: https://api.zeusia.app/docs

## 🆘 **Soporte**

Si encuentras problemas:

1. Revisa los logs en cada plataforma
2. Ejecuta el script de validación
3. Verifica las variables de entorno
4. Consulta la documentación de cada servicio
5. Abre un issue en el repositorio

---

**🎉 ¡Felicidades! Tu aplicación ZEUS-IA está ahora desplegada en producción.**
