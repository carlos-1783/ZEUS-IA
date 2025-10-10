@echo off
:: Script de instalación del servicio ZEUS IA
:: Debe ejecutarse como administrador

:: Verificar privilegios de administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Ejecutando con privilegios de administrador...
) else (
    echo ERROR: Este script debe ejecutarse como administrador.
    echo Por favor, haz clic derecho y selecciona "Ejecutar como administrador"
    pause
    exit /b 1
)

:: Configuración
set "SERVICE_NAME=ZEUS_IA_Backend"
set "PYTHON_PATH=C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe"
set "UVICORN_CMD=uvicorn"
set "HOST=0.0.0.0"
set "PORT=8000"
set "LOG_PATH=C:\logs"
set "PROJECT_PATH=C:\Users\Acer\ZEUS-IA\backend"

:: Crear directorio de logs si no existe
if not exist "%LOG_PATH%" mkdir "%LOG_PATH%"

echo ========================================
echo  Instalación del servicio ZEUS IA
echo ========================================

echo [1/5] Verificando NSSM...
where nssm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: NSSM no está instalado o no está en el PATH.
    echo Descarga NSSM de: https://nssm.cc/download
    echo Extrae nssm.exe a una carpeta en el PATH o al directorio actual.
    pause
    exit /b 1
)

echo [2/5] Deteniendo y eliminando servicio existente si existe...
sc query "%SERVICE_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo - Deteniendo servicio existente...
    net stop "%SERVICE_NAME%"
    timeout /t 2 >nul
    
    echo - Eliminando servicio existente...
    nssm remove "%SERVICE_NAME%" confirm
    timeout /t 1 >nul
)

echo [3/5] Instalando el servicio...
nssm install "%SERVICE_NAME%" "%PYTHON_PATH%" "-m %UVICORN_CMD% app.main:app --host %HOST% --port %PORT%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo instalar el servicio.
    pause
    exit /b 1
)

echo [4/5] Configurando el servicio...
nssm set "%SERVICE_NAME%" AppDirectory "%PROJECT_PATH%"
nssm set "%SERVICE_NAME%" AppNoConsole 1
nssm set "%SERVICE_NAME%" AppStdout "%LOG_PATH%\zeus_backend.log"
nssm set "%SERVICE_NAME%" AppStderr "%LOG_PATH%\zeus_backend_error.log"
nssm set "%SERVICE_NAME%" AppThrottle 15000
nssm set "%SERVICE_NAME%" AppStopMethodSkip 6
nssm set "%SERVICE_NAME%" Start SERVICE_AUTO_START

echo [5/5] Iniciando el servicio...
net start "%SERVICE_NAME%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo iniciar el servicio.
    echo Revisa los logs en %LOG_PATH%\zeus_backend_error.log
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Servicio instalado correctamente!
echo ========================================
echo.
echo [ACCESO RAPIDO]
echo - Interfaz Swagger: http://zeus.local:8000/docs
echo - API: http://zeus.local:8000/api/v1/
echo - Dashboard: http://zeus.local:8000/api/v1/dashboard
echo.
echo [LOGS]
echo - Logs: %LOG_PATH%\zeus_backend.log
echo - Errores: %LOG_PATH%\zeus_backend_error.log
echo.
echo [COMANDOS UTILES]
echo - Iniciar: net start ZEUS_IA_Backend
echo - Detener: net stop ZEUS_IA_Backend
echo - Estado: sc query ZEUS_IA_Backend
echo.
pause
