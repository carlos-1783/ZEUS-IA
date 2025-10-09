# 🌐 Configuración de Frontend en Vercel

## Paso 1: Crear cuenta en Vercel

1. **Ve a https://vercel.com**
2. **Crea una cuenta gratuita** (permite hasta 100 GB bandwidth/mes)
3. **Conecta tu cuenta de GitHub**

## Paso 2: Crear proyecto

1. **Haz clic en "New Project"**
2. **Selecciona tu repositorio ZEUS-IA**
3. **Configura el proyecto**:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm ci`

## Paso 3: Configurar variables de entorno

En el dashboard de Vercel, ve a **Settings > Environment Variables** y agrega:

```bash
# Configuración básica
VITE_API_URL=https://api.zeusia.app
VITE_WS_URL=wss://api.zeusia.app
VITE_ENVIRONMENT=production

# URLs del backend
VITE_BACKEND_URL=https://api.zeusia.app
VITE_API_BASE_URL=https://api.zeusia.app/api/v1

# Configuración PWA
VITE_APP_NAME=ZEUS-IA
VITE_APP_SHORT_NAME=ZEUS
VITE_APP_DESCRIPTION=Sistema de Inteligencia Artificial ZEUS
VITE_APP_VERSION=1.0.0

# Analytics (opcional)
VITE_GOOGLE_ANALYTICS_ID=your_ga_id_here
VITE_SENTRY_DSN=your_sentry_dsn_here

# Configuración de desarrollo
NODE_ENV=production
```

## Paso 4: Configurar dominio personalizado

1. **Ve a Settings > Domains**
2. **Agrega dominio**: `zeusia.app`
3. **Vercel generará automáticamente el certificado SSL**

## Paso 5: Configurar Vercel CLI (Opcional)

```bash
# Instalar Vercel CLI
npm install -g vercel

# Login
vercel login

# Desplegar
vercel --prod

# Ver logs
vercel logs
```

## Paso 6: Configurar PWA

El frontend ya está configurado como PWA. Vercel manejará automáticamente:

- ✅ **Service Worker**
- ✅ **Web App Manifest**
- ✅ **Offline functionality**
- ✅ **Caching strategies**

## Paso 7: Verificar despliegue

1. **Ve a la URL generada por Vercel**
2. **Verifica que la aplicación cargue correctamente**
3. **Verifica que PWA funcione** (instalar en móvil)
4. **Verifica la conexión al backend**

## Configuración de Build

Vercel detectará automáticamente que es un proyecto Vite y configurará:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "installCommand": "npm ci",
  "framework": "vite"
}
```

## Configuración de Headers

Vercel configurará automáticamente headers de seguridad:

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        },
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=31536000; includeSubDomains"
        }
      ]
    }
  ]
}
```

## Configuración de Caché

Vercel optimizará automáticamente el caché:

```json
{
  "routes": [
    {
      "src": "/static/(.*)",
      "headers": {
        "cache-control": "s-maxage=31536000,immutable"
      }
    }
  ]
}
```

## Límites de la cuenta gratuita

- ✅ **100 GB bandwidth/mes**
- ✅ **Unlimited deployments**
- ✅ **Dominio personalizado**
- ✅ **SSL automático**
- ✅ **CDN global**
- ✅ **Preview deployments**

## Próximos pasos

Una vez desplegado el frontend:

1. ✅ **Verifica que el frontend cargue**
2. ✅ **Configura el dominio personalizado**
3. ✅ **Verifica PWA en móvil**
4. 🚀 **Configura CI/CD con GitHub Actions**

## Comandos útiles

```bash
# Desplegar a producción
vercel --prod

# Desplegar preview
vercel

# Ver logs
vercel logs

# Ver información del proyecto
vercel inspect

# Ver dominios
vercel domains ls
```

## Solución de problemas

### Frontend no carga
1. **Verifica los logs**: `vercel logs`
2. **Verifica las variables de entorno**
3. **Verifica la configuración de build**

### Error de conexión al backend
1. **Verifica VITE_API_URL**
2. **Verifica CORS en el backend**
3. **Verifica que el backend esté desplegado**

### PWA no funciona
1. **Verifica el manifest.webmanifest**
2. **Verifica el service worker**
3. **Verifica HTTPS**

### Error de build
1. **Verifica las dependencias**
2. **Verifica la configuración de Vite**
3. **Verifica las variables de entorno**

## Configuración avanzada

### Custom Headers
```json
{
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        {
          "key": "Access-Control-Allow-Origin",
          "value": "https://zeusia.app"
        }
      ]
    }
  ]
}
```

### Redirects
```json
{
  "redirects": [
    {
      "source": "/old-path",
      "destination": "/new-path",
      "permanent": true
    }
  ]
}
```

### Rewrites
```json
{
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "https://api.zeusia.app/api/$1"
    }
  ]
}
```
