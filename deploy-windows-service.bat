@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  Configuración de ZEUS IA como Servicio Windows
echo ========================================

:: Verificar si se ejecuta como administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Ejecutando con privilegios de administrador
) else (
    echo [ERROR] Este script requiere privilegios de administrador.
    echo Por favor, ejecuta como administrador.
    pause
    exit /b 1
)

:: Variables de configuración
set "PROJECT_PATH=%~dp0backend"
set "SERVICE_NAME=ZEUS_IA_Backend"
set "PYTHON_PATH=%PROJECT_PATH%\venv\Scripts\python.exe"
set "UVICORN_CMD=uvicorn"
set "HOST=0.0.0.0"
set "PORT=8000"
set "LOG_PATH=C:\logs"
set "VENV_ACTIVATE=%PROJECT_PATH%\venv\Scripts\activate.bat"

:: Verificar si NSSM está instalado
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] NSSM no encontrado. Descargando e instalando...
    mkdir %TEMP%\nssm 2>nul
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip' -OutFile '%TEMP%\nssm.zip'"
    powershell -Command "Expand-Archive -Path '%TEMP%\nssm.zip' -DestinationPath '%TEMP%\nssm' -Force"
    copy "%TEMP%\nssm\nssm-2.24-101-g897c7ad\win64\nssm.exe" "%WINDIR%\System32\" >nul
    echo [OK] NSSM instalado correctamente
) else (
    echo [INFO] NSSM ya está instalado
)

:: Crear directorio de logs si no existe
if not exist "%LOG_PATH%" (
    mkdir "%LOG_PATH%"
    echo [INFO] Directorio de logs creado: %LOG_PATH%
)

:: Verificar si el servicio ya existe
sc query %SERVICE_NAME% >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Deteniendo y eliminando servicio existente...
    nssm stop %SERVICE_NAME%
    nssm remove %SERVICE_NAME% confirm
    timeout /t 2 >nul
)

echo [INFO] Creando nuevo servicio: %SERVICE_NAME%

:: Crear script de inicio
set "START_SCRIPT=%TEMP%\start_zeus.bat"
echo @echo off > "%START_SCRIPT%"
echo call "%VENV_ACTIVATE%" >> "%START_SCRIPT%"
echo cd /d "%PROJECT_PATH%" >> "%START_SCRIPT%"
echo "%PYTHON_PATH%" -m %UVICORN_CMD% app.main:app --host %HOST% --port %PORT% >> "%START_SCRIPT%"

:: Crear el servicio con NSSM
nssm install %SERVICE_NAME% "%COMSPEC%" "/c ""%START_SCRIPT%""

:: Configurar el directorio de trabajo
nssm set %SERVICE_NAME% AppDirectory "%PROJECT_PATH%"

:: Configurar el entorno
nssm set %SERVICE_NAME% AppEnvironmentExtra "PYTHONPATH=%PROJECT_PATH%"
nssm set %SERVICE_NAME% AppNoConsole 1

:: Configurar el usuario (opcional, descomentar si es necesario)
:: nssm set %SERVICE_NAME% ObjectName ".\Usuario" "Contraseña"

:: Configurar para reiniciar automáticamente
nssm set %SERVICE_NAME% AppRestartDelay 5000
nssm set %SERVICE_NAME% AppStdout "%LOG_PATH%\zeus_backend.log"
nssm set %SERVICE_NAME% AppStderr "%LOG_PATH%\zeus_backend_error.log"

:: Configurar para inicio automático
echo [INFO] Configurando para inicio automático...
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

:: Configurar tiempo de espera para el servicio
nssm set %SERVICE_NAME% AppThrottle 15000
nssm set %SERVICE_NAME% AppStopMethodSkip 6

:: Iniciar el servicio
echo [INFO] Iniciando el servicio...
timeout /t 2 >nul
net start %SERVICE_NAME% 2>&1 | findstr /C:"service" >nul
if %errorlevel% equ 0 (
    echo [ERROR] No se pudo iniciar el servicio. Verificando logs...
    type "%LOG_PATH%\zeus_backend_error.log" 2>nul || echo No se encontraron logs de error.
    echo.
    echo [SUGERENCIA] Intenta iniciar manualmente con: net start %SERVICE_NAME%
) else (
    echo [OK] Servicio iniciado correctamente
)

:: Agregar regla de firewall
echo [INFO] Configurando firewall...
netsh advfirewall firewall add rule name="ZEUS IA Backend" dir=in action=allow protocol=TCP localport=%PORT% profile=any

:: Agregar entrada al archivo hosts
echo [INFO] Actualizando archivo hosts...
echo 127.0.0.1    zeus.local >> %windir%\System32\drivers\etc\hosts

echo.
echo ========================================
echo  Configuración completada exitosamente!
echo ========================================
echo.
echo [ACCESO RÁPIDO]
echo - Interfaz Swagger: http://zeus.local:%PORT%/docs
echo - API: http://zeus.local:%PORT%/api/v1/
echo - Dashboard: http://zeus.local:%PORT%/api/v1/dashboard
echo.
echo [RUTAS IMPORTANTES]
echo - Logs de la aplicación: %LOG_PATH%\zeus_backend.log
echo - Errores: %LOG_PATH%\zeus_backend_error.log
echo.
echo [COMANDOS ÚTILES]
echo - Iniciar servicio: net start %SERVICE_NAME%
echo - Detener servicio: net stop %SERVICE_NAME%
echo - Ver estado: sc query %SERVICE_NAME%
echo - Ver logs: type "%LOG_PATH%\zeus_backend.log"
echo.
pause
