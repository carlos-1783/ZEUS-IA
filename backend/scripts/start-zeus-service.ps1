# Requiere ejecución como administrador
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "Por favor, ejecuta este script como administrador"
    exit 1
}

# Variables
$serviceName = "ZEUS_IA_Backend"
$projectPath = "$PSScriptRoot\backend"
$pythonPath = "$projectPath\venv\Scripts\python.exe"
$uvicornCmd = "uvicorn"
$hostAddress = "0.0.0.0"
$port = 8000
$logPath = "C:\logs"

# Crear directorio de logs si no existe
if (-not (Test-Path $logPath)) {
    New-Item -ItemType Directory -Path $logPath | Out-Null
}

# Detener y eliminar el servicio si existe
if (Get-Service $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Deteniendo y eliminando el servicio existente..."
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    & nssm remove $serviceName confirm
    Start-Sleep -Seconds 1
}

# Crear script de inicio
$startScript = @"
@echo off
call "$projectPath\venv\Scripts\activate.bat"
cd /d "$projectPath"
"$pythonPath" -m $uvicornCmd app.main:app --host $hostAddress --port $port
"@

$startScriptPath = "$env:TEMP\start_zeus_service.bat"
$startScript | Out-File -FilePath $startScriptPath -Encoding ascii

# Instalar el servicio con NSSM
Write-Host "Instalando el servicio..."
& nssm install $serviceName "$env:ComSpec" "/c `"$startScriptPath`""
& nssm set $serviceName AppDirectory "$projectPath"
& nssm set $serviceName AppEnvironmentExtra "PYTHONPATH=$projectPath"
& nssm set $serviceName AppNoConsole 1
& nssm set $serviceName AppStdout "$logPath\zeus_backend.log"
& nssm set $serviceName AppStderr "$logPath\zeus_backend_error.log"
& nssm set $serviceName AppThrottle 15000
& nssm set $serviceName AppStopMethodSkip 6
& nssm set $serviceName Start SERVICE_AUTO_START

# Iniciar el servicio
Write-Host "Iniciando el servicio..."
Start-Service -Name $serviceName

# Verificar estado
Start-Sleep -Seconds 2
$service = Get-Service -Name $serviceName
Write-Host "Estado del servicio: $($service.Status)"

# Mostrar información de conexión
Write-Host "`n[ACCESO RÁPIDO]"
Write-Host "- Interfaz Swagger: http://zeus.local:$port/docs"
Write-Host "- API: http://zeus.local:$port/api/v1/"
Write-Host "- Dashboard: http://zeus.local:$port/api/v1/dashboard"
Write-Host "`n[LOGS]"
Write-Host "- Logs de la aplicación: $logPath\zeus_backend.log"
Write-Host "- Errores: $logPath\zeus_backend_error.log"

# Verificar si responde
Write-Host "`nVerificando si el servicio responde..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$port/api/v1/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ El servicio está funcionando correctamente!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  El servicio responde con estado: $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ No se pudo conectar al servicio: $_" -ForegroundColor Red
    Write-Host "Revisa los logs en $logPath\zeus_backend_error.log"
}
