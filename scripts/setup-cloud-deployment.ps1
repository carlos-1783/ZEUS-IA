# ===============================================
# ZEUS-IA - Script de Configuración Cloud Deployment
# ===============================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Environment = "production",
    
    [Parameter(Mandatory=$false)]
    [switch]$SetupDatabase = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SetupBackend = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SetupFrontend = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$All = $false
)

# Colores para output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"
$White = "White"

function Write-Log {
    param([string]$Message, [string]$Color = $White)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-Log "✅ $Message" $Green
}

function Write-Error {
    param([string]$Message)
    Write-Log "❌ $Message" $Red
    exit 1
}

function Write-Warning {
    param([string]$Message)
    Write-Log "⚠️  $Message" $Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Log "ℹ️  $Message" $Blue
}

# Verificar prerequisitos
function Test-Prerequisites {
    Write-Info "Verificando prerequisitos..."
    
    # Verificar Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker no está instalado. Instala Docker Desktop primero."
    }
    
    # Verificar Node.js
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Error "Node.js no está instalado. Instala Node.js 18+ primero."
    }
    
    # Verificar npm
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Error "npm no está instalado."
    }
    
    # Verificar Python
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Python no está instalado. Instala Python 3.11+ primero."
    }
    
    Write-Success "Todos los prerequisitos están instalados"
}

# Configurar base de datos en Neon
function Setup-NeonDatabase {
    Write-Info "Configurando base de datos en Neon..."
    
    # Crear archivo de configuración para Neon
    $neonConfig = @"
# Configuración de Neon Database
NEON_DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
NEON_POOLER_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require`&pgbouncer=true

# Variables de entorno para producción
DATABASE_URL=`$NEON_DATABASE_URL
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
"@
    
    $neonConfig | Out-File -FilePath "neon.env" -Encoding UTF8
    
    Write-Info "1. Ve a https://neon.tech y crea una nueva base de datos"
    Write-Info "2. Copia la URL de conexión"
    Write-Info "3. Actualiza el archivo neon.env con tu URL real"
    Write-Info "4. Ejecuta las migraciones: python backend/scripts/migrate.py"
    
    Write-Warning "Archivo neon.env creado. Actualiza con tu configuración real."
}

# Configurar backend en Railway
function Setup-RailwayBackend {
    Write-Info "Configurando backend en Railway..."
    
    # Crear archivo de configuración para Railway
    $railwayConfig = @"
# Configuración de Railway
RAILWAY_TOKEN=your_railway_token_here
RAILWAY_PROJECT_ID=your_project_id_here

# Variables de entorno para Railway
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=`${{NEON_DATABASE_URL}}
REDIS_URL=`${{REDIS_URL}}
SECRET_KEY=`${{SECRET_KEY}}
"@
    
    $railwayConfig | Out-File -FilePath "railway.env" -Encoding UTF8
    
    Write-Info "1. Ve a https://railway.app y crea una nueva cuenta"
    Write-Info "2. Instala Railway CLI: npm install -g @railway/cli"
    Write-Info "3. Login: railway login"
    Write-Info "4. Crear proyecto: railway init"
    Write-Info "5. Desplegar: railway up"
    
    Write-Warning "Archivo railway.env creado. Configura con tus credenciales reales."
}

# Configurar frontend en Vercel
function Setup-VercelFrontend {
    Write-Info "Configurando frontend en Vercel..."
    
    # Crear archivo de configuración para Vercel
    $vercelConfig = @"
# Configuración de Vercel
VERCEL_TOKEN=your_vercel_token_here
VERCEL_ORG_ID=your_org_id_here
VERCEL_PROJECT_ID=your_project_id_here

# Variables de entorno para Vercel
VITE_API_URL=https://api.zeusia.app
VITE_WS_URL=wss://api.zeusia.app
VITE_ENVIRONMENT=production
"@
    
    $vercelConfig | Out-File -FilePath "vercel.env" -Encoding UTF8
    
    # Crear archivo de configuración de Vercel
    $vercelJson = @"
{
  "version": 2,
  "name": "zeus-ia-frontend",
  "builds": [
    {
      "src": "frontend/package.json",
      "use": "@vercel/static-build",
      "config": {
        "distDir": "dist"
      }
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "headers": {
        "cache-control": "s-maxage=31536000,immutable"
      }
    },
    {
      "src": "/(.*)",
      "dest": "/index.html"
    }
  ],
  "env": {
    "VITE_API_URL": "https://api.zeusia.app",
    "VITE_WS_URL": "wss://api.zeusia.app"
  }
}
"@
    
    $vercelJson | Out-File -FilePath "vercel.json" -Encoding UTF8
    
    Write-Info "1. Ve a https://vercel.com y crea una nueva cuenta"
    Write-Info "2. Instala Vercel CLI: npm install -g vercel"
    Write-Info "3. Login: vercel login"
    Write-Info "4. Desplegar: vercel --prod"
    
    Write-Warning "Archivos vercel.env y vercel.json creados."
}

# Configurar dominio personalizado
function Setup-CustomDomain {
    Write-Info "Configurando dominio personalizado..."
    
    Write-Info "1. Compra el dominio zeusia.app en tu proveedor preferido"
    Write-Info "2. Configura DNS:"
    Write-Info "   - A record: @ -> IP del servidor"
    Write-Info "   - CNAME: www -> zeusia.app"
    Write-Info "   - CNAME: api -> railway.app"
    Write-Info "3. Configura SSL con Let's Encrypt"
    Write-Info "4. Actualiza variables de entorno con el dominio real"
}

# Configurar monitoreo
function Setup-Monitoring {
    Write-Info "Configurando monitoreo..."
    
    $monitoringConfig = @"
# Configuración de monitoreo
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true
LOG_LEVEL=INFO

# Uptime monitoring
UPTIME_ROBOT_API_KEY=your_uptime_robot_key
UPTIME_ROBOT_MONITOR_URLS=https://zeusia.app,https://api.zeusia.app

# Error tracking
SENTRY_DSN=your_sentry_dsn_here

# Analytics
GOOGLE_ANALYTICS_ID=your_ga_id_here
"@
    
    $monitoringConfig | Out-File -FilePath "monitoring.env" -Encoding UTF8
    
    Write-Info "1. Configura Uptime Robot para monitorear uptime"
    Write-Info "2. Configura Sentry para tracking de errores"
    Write-Info "3. Configura Google Analytics para métricas"
    
    Write-Warning "Archivo monitoring.env creado."
}

# Función principal
function Main {
    Write-Log "🚀 Configurando despliegue en la nube para ZEUS-IA" $Blue
    
    Test-Prerequisites
    
    if ($All -or $SetupDatabase) {
        Setup-NeonDatabase
    }
    
    if ($All -or $SetupBackend) {
        Setup-RailwayBackend
    }
    
    if ($All -or $SetupFrontend) {
        Setup-VercelFrontend
    }
    
    if ($All) {
        Setup-CustomDomain
        Setup-Monitoring
    }
    
    Write-Success "Configuración completada!"
    Write-Info "Próximos pasos:"
    Write-Info "1. Actualiza los archivos de configuración con tus credenciales reales"
    Write-Info "2. Ejecuta los scripts de despliegue"
    Write-Info "3. Configura tu dominio personalizado"
    Write-Info "4. Activa el monitoreo"
    
    Write-Log "📚 Documentación completa disponible en DEPLOYMENT.md" $Blue
}

# Ejecutar función principal
Main
