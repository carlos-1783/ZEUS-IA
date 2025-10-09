# ===============================================
# ZEUS-IA - Script de Configuración de Despliegue
# ===============================================

Write-Host "🚀 Configurando despliegue en la nube para ZEUS-IA" -ForegroundColor Blue

# Verificar prerequisitos
Write-Host "Verificando prerequisitos..." -ForegroundColor Yellow

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker no está instalado. Instala Docker Desktop primero." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Node.js no está instalado. Instala Node.js 18+ primero." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python no está instalado. Instala Python 3.11+ primero." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Todos los prerequisitos están instalados" -ForegroundColor Green

# Crear archivos de configuración
Write-Host "Creando archivos de configuración..." -ForegroundColor Yellow

# Archivo de configuración para Neon
$neonConfig = @"
# Configuración de Neon Database
NEON_DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
NEON_POOLER_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require&pgbouncer=true

# Variables de entorno para producción
DATABASE_URL=$NEON_DATABASE_URL
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
"@

$neonConfig | Out-File -FilePath "neon.env" -Encoding UTF8

# Archivo de configuración para Railway
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

# Archivo de configuración para Vercel
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

Write-Host "✅ Archivos de configuración creados" -ForegroundColor Green

# Mostrar instrucciones
Write-Host ""
Write-Host "📋 Próximos pasos:" -ForegroundColor Blue
Write-Host ""
Write-Host "1. 🗄️  Configurar Base de Datos (Neon):" -ForegroundColor Yellow
Write-Host "   - Ve a https://neon.tech y crea una nueva base de datos"
Write-Host "   - Copia la URL de conexión"
Write-Host "   - Actualiza el archivo neon.env con tu URL real"
Write-Host ""
Write-Host "2. 🚂 Configurar Backend (Railway):" -ForegroundColor Yellow
Write-Host "   - Ve a https://railway.app y crea una nueva cuenta"
Write-Host "   - Instala Railway CLI: npm install -g @railway/cli"
Write-Host "   - Login: railway login"
Write-Host "   - Crear proyecto: railway init"
Write-Host ""
Write-Host "3. 🌐 Configurar Frontend (Vercel):" -ForegroundColor Yellow
Write-Host "   - Ve a https://vercel.com y crea una nueva cuenta"
Write-Host "   - Instala Vercel CLI: npm install -g vercel"
Write-Host "   - Login: vercel login"
Write-Host "   - Desplegar: vercel --prod"
Write-Host ""
Write-Host "4. 🔐 Configurar Dominio:" -ForegroundColor Yellow
Write-Host "   - Compra el dominio zeusia.app"
Write-Host "   - Configura DNS: A record -> IP del servidor"
Write-Host "   - Configura SSL automáticamente"
Write-Host ""
Write-Host "5. 🔄 Configurar CI/CD:" -ForegroundColor Yellow
Write-Host "   - Configura secrets en GitHub"
Write-Host "   - El archivo .github/workflows/deploy.yml ya está listo"
Write-Host "   - Haz push a main para activar el despliegue"
Write-Host ""
Write-Host "6. 🧪 Validar Despliegue:" -ForegroundColor Yellow
Write-Host "   - Ejecuta: .\scripts\validate-production.ps1"
Write-Host "   - Verifica todas las funcionalidades"
Write-Host ""
Write-Host "📚 Documentación completa disponible en DEPLOYMENT_CLOUD.md" -ForegroundColor Blue
Write-Host ""
Write-Host "🎉 ¡Configuración completada!" -ForegroundColor Green
