# ===============================================
# ZEUS-IA - Script de Validación de Despliegue
# ===============================================

param(
    [Parameter(Mandatory=$false)]
    [string]$FrontendUrl = "https://zeusia.app",
    
    [Parameter(Mandatory=$false)]
    [string]$BackendUrl = "https://api.zeusia.app"
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

function Test-Url {
    param(
        [string]$Url,
        [string]$Description
    )
    
    Write-Info "Probando: $Description"
    Write-Info "URL: $Url"
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 30
        if ($response.StatusCode -eq 200) {
            Write-Success "$Description - Status: $($response.StatusCode)"
            return $true
        } else {
            Write-Warning "$Description - Status: $($response.StatusCode)"
            return $false
        }
    }
    catch {
        Write-Error "$Description - Error: $($_.Exception.Message)"
        return $false
    }
}

function Main {
    Write-Log "🔍 Validando despliegue de ZEUS-IA" $Blue
    Write-Info "Frontend: $FrontendUrl"
    Write-Info "Backend: $BackendUrl"
    Write-Log "=" * 50 $Blue
    
    $allTestsPassed = $true
    
    # Test 1: Frontend
    if (-not (Test-Url -Url $FrontendUrl -Description "Frontend")) {
        $allTestsPassed = $false
    }
    
    # Test 2: Backend Health Check
    if (-not (Test-Url -Url "$BackendUrl/health" -Description "Backend Health Check")) {
        $allTestsPassed = $false
    }
    
    # Test 3: API Documentation
    if (-not (Test-Url -Url "$BackendUrl/docs" -Description "API Documentation")) {
        $allTestsPassed = $false
    }
    
    # Test 4: API Endpoints
    if (-not (Test-Url -Url "$BackendUrl/api/v1/health" -Description "API Health Check")) {
        $allTestsPassed = $false
    }
    
    # Test 5: PWA Manifest
    if (-not (Test-Url -Url "$FrontendUrl/manifest.webmanifest" -Description "PWA Manifest")) {
        Write-Warning "PWA Manifest no encontrado"
    }
    
    # Test 6: Service Worker
    if (-not (Test-Url -Url "$FrontendUrl/sw.js" -Description "Service Worker")) {
        Write-Warning "Service Worker no encontrado"
    }
    
    Write-Log "=" * 50 $Blue
    Write-Log "📊 Resumen de validación:" $Blue
    
    if ($allTestsPassed) {
        Write-Success "🎉 ¡Despliegue validado exitosamente!"
        Write-Success "✅ ZEUS-IA está funcionando correctamente"
    } else {
        Write-Warning "⚠️  Algunas validaciones fallaron"
        Write-Warning "Revisa los logs arriba para más detalles"
    }
    
    Write-Log "" $White
    Write-Info "📱 URLs de acceso:"
    Write-Info "   Frontend: $FrontendUrl"
    Write-Info "   Backend: $BackendUrl"
    Write-Info "   Health Check: $BackendUrl/health"
    Write-Info "   API Docs: $BackendUrl/docs"
    
    Write-Log "" $White
    Write-Info "🔧 Próximos pasos:"
    Write-Info "   1. Configura el dominio personalizado"
    Write-Info "   2. Configura SSL/TLS"
    Write-Info "   3. Configura monitoreo"
    Write-Info "   4. Configura CI/CD"
    
    Write-Log "" $White
    Write-Log "📚 Documentación completa disponible en DEPLOYMENT_CLOUD.md" $Blue
}

# Ejecutar función principal
Main
