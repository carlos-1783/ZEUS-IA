# Requiere ejecución como administrador
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "Por favor, ejecuta este script como administrador"
    exit 1
}

# Configuración
$serviceName = "ZEUS_IA_Backend"
$configFile = "$PSScriptRoot\zeus-service-config.ini"
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

# Instalar el servicio usando la configuración
Write-Host "Instalando el servicio con la configuración de $configFile..."
& nssm install $serviceName

# Aplicar la configuración desde el archivo INI
Get-Content $configFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -match '^([^=]+)=(.*)$') {
        $param = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Expandir variables de entorno
        $value = [System.Environment]::ExpandEnvironmentVariables($value)
        
        # Aplicar configuración
        if ($param -eq 'nssm') { return }  # Saltar línea [nssm]
        Write-Host "Configurando $param = $value"
        & nssm set $serviceName $param $value
    }
}

# Iniciar el servicio
Write-Host "Iniciando el servicio..."
Start-Service -Name $serviceName

# Verificar estado
Start-Sleep -Seconds 2
$service = Get-Service -Name $serviceName
Write-Host "Estado del servicio: $($service.Status)"

# Mostrar información de conexión
Write-Host "`n[ACCESO RÁPIDO]"
Write-Host "- Interfaz Swagger: http://zeus.local:8000/docs"
Write-Host "- API: http://zeus.local:8000/api/v1/"
Write-Host "- Dashboard: http://zeus.local:8000/api/v1/dashboard"
Write-Host "`n[LOGS]"
Write-Host "- Logs de la aplicación: $logPath\zeus_backend.log"
Write-Host "- Errores: $logPath\zeus_backend_error.log"

# Verificar si responde
Write-Host "`nVerificando si el servicio responde..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ El servicio está funcionando correctamente!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  El servicio responde con estado: $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ No se pudo conectar al servicio: $_" -ForegroundColor Red
    Write-Host "Revisa los logs en $logPath\zeus_backend_error.log"
    
    # Mostrar las últimas líneas del log de errores
    if (Test-Path "$logPath\zeus_backend_error.log") {
        Write-Host "`nÚltimas líneas del log de errores:"
        Get-Content "$logPath\zeus_backend_error.log" -Tail 10
    }
}
