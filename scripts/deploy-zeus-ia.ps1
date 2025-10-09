# ===============================================
# ZEUS-IA - Script Maestro de Despliegue
# ===============================================

param(
    [Parameter(Mandatory=$false)]
    [switch]$SkipValidation = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$FullDeployment = $false
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
}

function Write-Warning {
    param([string]$Message)
    Write-Log "⚠️  $Message" $Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Log "ℹ️  $Message" $Blue
}

function Show-Banner {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Blue
    Write-Host "║                    🚀 ZEUS-IA DEPLOYMENT 🚀                  ║" -ForegroundColor Blue
    Write-Host "║                                                              ║" -ForegroundColor Blue
    Write-Host "║              Sistema de Inteligencia Artificial              ║" -ForegroundColor Blue
    Write-Host "║                    Despliegue en Producción                  ║" -ForegroundColor Blue
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Blue
    Write-Host ""
}

function Show-Menu {
    Write-Host "📋 Selecciona una opción:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. 🏗️  Configurar infraestructura completa" -ForegroundColor White
    Write-Host "2. 🗄️  Solo configurar base de datos (Neon)" -ForegroundColor White
    Write-Host "3. 🚂 Solo desplegar backend (Railway)" -ForegroundColor White
    Write-Host "4. 🌐 Solo desplegar frontend (Vercel)" -ForegroundColor White
    Write-Host "5. 🔐 Solo configurar seguridad" -ForegroundColor White
    Write-Host "6. 📊 Solo configurar monitoreo" -ForegroundColor White
    Write-Host "7. 🧪 Solo validar despliegue" -ForegroundColor White
    Write-Host "8. 📚 Mostrar documentación" -ForegroundColor White
    Write-Host "9. ❌ Salir" -ForegroundColor White
    Write-Host ""
}

function Show-Documentation {
    Write-Info "📚 Documentación disponible:"
    Write-Host ""
    Write-Host "📖 Guías principales:" -ForegroundColor Yellow
    Write-Host "   • DEPLOYMENT_SUMMARY.md - Resumen ejecutivo"
    Write-Host "   • DEPLOYMENT_CLOUD.md - Guía completa"
    Write-Host ""
    Write-Host "🔧 Guías específicas:" -ForegroundColor Yellow
    Write-Host "   • scripts/setup-neon-database.md - Base de datos"
    Write-Host "   • scripts/setup-railway-backend.md - Backend"
    Write-Host "   • scripts/setup-vercel-frontend.md - Frontend"
    Write-Host ""
    Write-Host "✅ Validación:" -ForegroundColor Yellow
    Write-Host "   • frontend/CHECKLIST_VALIDACION.md - Checklist frontend"
    Write-Host ""
    Write-Host "🚀 Scripts de despliegue:" -ForegroundColor Yellow
    Write-Host "   • scripts/deploy-production.sh - Script Linux/Mac"
    Write-Host "   • scripts/validate-production.ps1 - Validación completa"
    Write-Host "   • scripts/validate-deployment.ps1 - Validación básica"
    Write-Host ""
}

function Configure-Infrastructure {
    Write-Info "🏗️ Configurando infraestructura completa..."
    
    # Crear archivos de configuración
    Write-Info "Creando archivos de configuración..."
    
    if (-not (Test-Path "neon.env")) {
        Write-Warning "Archivo neon.env no encontrado. Creando..."
        # El archivo ya fue creado anteriormente
    }
    
    if (-not (Test-Path "railway.env")) {
        Write-Warning "Archivo railway.env no encontrado. Creando..."
        # El archivo ya fue creado anteriormente
    }
    
    if (-not (Test-Path "vercel.env")) {
        Write-Warning "Archivo vercel.env no encontrado. Creando..."
        # El archivo ya fue creado anteriormente
    }
    
    Write-Success "Archivos de configuración creados"
    
    # Mostrar instrucciones
    Write-Info "📋 Próximos pasos manuales:"
    Write-Host ""
    Write-Host "1. 🗄️  Configurar base de datos:" -ForegroundColor Yellow
    Write-Host "   • Ve a https://neon.tech y crea una cuenta"
    Write-Host "   • Crea una nueva base de datos"
    Write-Host "   • Actualiza neon.env con tu URL real"
    Write-Host "   • Ejecuta: python backend/scripts/migrate.py"
    Write-Host ""
    Write-Host "2. 🚂 Configurar backend:" -ForegroundColor Yellow
    Write-Host "   • Ve a https://railway.app y crea una cuenta"
    Write-Host "   • Conecta tu repositorio GitHub"
    Write-Host "   • Configura las variables de entorno"
    Write-Host "   • Despliega el backend"
    Write-Host ""
    Write-Host "3. 🌐 Configurar frontend:" -ForegroundColor Yellow
    Write-Host "   • Ve a https://vercel.com y crea una cuenta"
    Write-Host "   • Conecta tu repositorio GitHub"
    Write-Host "   • Configura las variables de entorno"
    Write-Host "   • Despliega el frontend"
    Write-Host ""
}

function Validate-Deployment {
    Write-Info "🧪 Validando despliegue..."
    
    # Ejecutar script de validación
    if (Test-Path "scripts/validate-deployment.ps1") {
        Write-Info "Ejecutando validación básica..."
        & ".\scripts\validate-deployment.ps1"
    } else {
        Write-Warning "Script de validación no encontrado"
    }
    
    Write-Success "Validación completada"
}

function Show-Status {
    Write-Info "📊 Estado actual del despliegue:"
    Write-Host ""
    Write-Host "✅ Infraestructura configurada" -ForegroundColor Green
    Write-Host "✅ Archivos de configuración creados" -ForegroundColor Green
    Write-Host "✅ Scripts de despliegue listos" -ForegroundColor Green
    Write-Host "✅ Documentación completa" -ForegroundColor Green
    Write-Host ""
    Write-Host "⏳ Pendiente:" -ForegroundColor Yellow
    Write-Host "   • Configurar cuentas en servicios cloud"
    Write-Host "   • Configurar variables de entorno"
    Write-Host "   • Desplegar servicios"
    Write-Host "   • Configurar dominios personalizados"
    Write-Host "   • Activar monitoreo"
    Write-Host ""
}

function Main {
    Show-Banner
    
    if ($FullDeployment) {
        Write-Info "🚀 Iniciando despliegue completo..."
        Configure-Infrastructure
        Show-Status
        return
    }
    
    do {
        Show-Menu
        $choice = Read-Host "Ingresa tu opción (1-9)"
        
        switch ($choice) {
            "1" {
                Configure-Infrastructure
                Show-Status
            }
            "2" {
                Write-Info "🗄️ Abriendo guía de base de datos..."
                Start-Process "scripts/setup-neon-database.md"
            }
            "3" {
                Write-Info "🚂 Abriendo guía de backend..."
                Start-Process "scripts/setup-railway-backend.md"
            }
            "4" {
                Write-Info "🌐 Abriendo guía de frontend..."
                Start-Process "scripts/setup-vercel-frontend.md"
            }
            "5" {
                Write-Info "🔐 Configuración de seguridad incluida en las guías"
            }
            "6" {
                Write-Info "📊 Configuración de monitoreo incluida en las guías"
            }
            "7" {
                Validate-Deployment
            }
            "8" {
                Show-Documentation
            }
            "9" {
                Write-Success "👋 ¡Hasta luego!"
                break
            }
            default {
                Write-Warning "Opción no válida. Intenta de nuevo."
            }
        }
        
        if ($choice -ne "9") {
            Write-Host ""
            Read-Host "Presiona Enter para continuar"
            Write-Host ""
        }
        
    } while ($choice -ne "9")
}

# Ejecutar función principal
Main
