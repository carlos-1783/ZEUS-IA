# Script para iniciar el backend de ZEUS-IA
# Guardar este archivo como start-backend.ps1 y ejecutarlo con PowerShell

# Configuración
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectDir "backend"
$logDir = Join-Path $projectDir "logs"
$logFile = Join-Path $logDir "backend-startup.log"
$venvDir = Join-Path $backendDir "venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$pipExe = Join-Path $venvDir "Scripts\pip.exe"

# Función para escribir en el log
function Write-Log {
    param([string]$message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $message"
    # Mostrar en consola con colores
    if ($message -match "\[ERROR\]") {
        Write-Host $logMessage -ForegroundColor Red
    } elseif ($message -match "\[WARNING\]") {
        Write-Host $logMessage -ForegroundColor Yellow
    } else {
        Write-Host $logMessage -ForegroundColor Green
    }
    # También escribir en el archivo de log
    Add-Content -Path $logFile -Value $logMessage -ErrorAction SilentlyContinue
}

# Crear directorio de logs si no existe
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
    Write-Log "Directorio de logs creado en: $logDir"
}

Write-Log "=== INICIANDO ZEUS-IA BACKEND ==="
Write-Log "Directorio del proyecto: $projectDir"
Write-Log "Directorio del backend: $backendDir"

# Verificar que el directorio del backend existe
if (-not (Test-Path $backendDir)) {
    Write-Log "[ERROR] No se encontró el directorio del backend en: $backendDir"
    exit 1
}

# Cambiar al directorio del backend
Set-Location $backendDir
Write-Log "Directorio actual: $(Get-Location)"

# Verificar si el entorno virtual existe
if (-not (Test-Path $venvDir)) {
    Write-Log "Creando entorno virtual de Python en: $venvDir"
    try {
        python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw "Error al crear el entorno virtual" }
        
        # Activar el entorno virtual
        & $pythonExe -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw "Error al actualizar pip" }
        
        # Instalar dependencias
        Write-Log "Instalando dependencias..."
        & $pipExe install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Error al instalar las dependencias" }
        
        Write-Log "Entorno virtual y dependencias instaladas correctamente"
    }
    catch {
        Write-Log "[ERROR] Error al configurar el entorno virtual: $_"
        exit 1
    }
}

# Verificar si uvicorn está instalado
$uvicornCheck = & $pythonExe -c "import pkg_resources; print('uvicorn' in {pkg.key.lower() for pkg in pkg_resources.working_set})" 2>$null
if ($uvicornCheck -eq "False") {
    Write-Log "Instalando uvicorn..."
    & $pipExe install uvicorn[standard]
    if ($LASTEXITCODE -ne 0) {
        Write-Log "[ERROR] No se pudo instalar uvicorn"
        exit 1
    }
}

# Iniciar el servidor
Write-Log "Iniciando el servidor backend..."
Write-Log "URL de la API: http://localhost:8000"
Write-Log "Documentación de la API: http://localhost:8000/docs"
Write-Log "Registros: $logFile"
Write-Log ""
Write-Log "Presiona Ctrl+C para detener el servidor."
Write-Log ""

# Iniciar el servidor con uvicorn
Write-Log "Iniciando servidor Uvicorn..."
try {
    $process = Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -NoNewWindow -PassThru -RedirectStandardOutput "$logDir\uvicorn_stdout.log" -RedirectStandardError "$logDir\uvicorn_stderr.log"
    
    Write-Log "Proceso Uvicorn iniciado con ID: $($process.Id)"
    Write-Log "Puedes ver los logs en tiempo real en:"
    Write-Log "- Salida estándar: $logDir\uvicorn_stdout.log"
    Write-Log "- Errores: $logDir\uvicorn_stderr.log"
    Write-Log ""
    Write-Log "Presiona Ctrl+C para detener el servidor"
    
    # Mantener el script en ejecución
    $process.WaitForExit()
    
    if ($process.ExitCode -ne 0) {
        Write-Log "[ERROR] El servidor se detuvo con el código de salida: $($process.ExitCode)"
        Get-Content "$logDir\uvicorn_stderr.log" -Tail 20 | ForEach-Object { Write-Log "[UVICORN ERROR] $_" }
        exit $process.ExitCode
    }
}
catch {
    Write-Log "[ERROR] Error al iniciar el servidor: $_"
    exit 1
}
