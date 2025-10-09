# Script para iniciar la aplicación ZEUS-IA con Docker Compose
# Este script verifica que Docker esté en ejecución y luego inicia los servicios

# Establecer la política de ejecución para el ámbito actual
Set-ExecutionPolicy Bypass -Scope Process -Force

# Función para verificar si Docker está en ejecución
function Test-DockerRunning {
    try {
        docker info *>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

# Función para mostrar un mensaje de error
function Show-Error {
    param([string]$message)
    Write-Host "Error: $message" -ForegroundColor Red
    exit 1
}

# Obtener el directorio del script
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath

# Cambiar al directorio del script
Set-Location $scriptDir

# Verificar si Docker está en ejecución
if (-not (Test-DockerRunning)) {
    Show-Error "Docker no está en ejecución. Por favor, inicia Docker Desktop y vuelve a intentarlo."
}

Write-Host "Iniciando ZEUS-IA con Docker Compose..." -ForegroundColor Cyan
Write-Host "Directorio actual: $scriptDir" -ForegroundColor Yellow

# Verificar si existe el archivo docker-compose.yml
if (-not (Test-Path "$scriptDir\docker-compose.yml")) {
    Show-Error "No se encontró el archivo docker-compose.yml en el directorio $scriptDir"
}

try {
    # Detener y eliminar contenedores existentes
    Write-Host "`nDeteniendo contenedores existentes..." -ForegroundColor Yellow
    docker-compose -f "$scriptDir\docker-compose.yml" down
    
    # Construir las imágenes
    Write-Host "`nConstruyendo imágenes..." -ForegroundColor Yellow
    docker-compose -f "$scriptDir\docker-compose.yml" build --no-cache
    
    # Iniciar los servicios
    Write-Host "`nIniciando servicios..." -ForegroundColor Yellow
    docker-compose -f "$scriptDir\docker-compose.yml" up -d
    
    # Esperar un momento para que los contenedores se inicien
    Start-Sleep -Seconds 5
    
    # Mostrar información de los contenedores
    Write-Host "`nContenedores en ejecución:" -ForegroundColor Green
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # Mostrar URLs de acceso
    Write-Host "`nAplicación desplegada correctamente!" -ForegroundColor Green
    Write-Host "- Frontend: http://localhost:5173" -ForegroundColor Cyan
    Write-Host "- Backend API: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "- Documentación de la API: http://localhost:8000/docs" -ForegroundColor Cyan
    
    # Abrir el navegador con el frontend
    Write-Host "`nAbriendo el navegador..." -ForegroundColor Yellow
    Start-Process "http://localhost:5173"
    
} catch {
    Show-Error "Error al iniciar la aplicación: $_"
}

# Mantener la ventana abierta
Write-Host "`nPresiona cualquier tecla para continuar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
