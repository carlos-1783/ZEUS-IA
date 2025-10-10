@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

:: ============================================
:: ZEUS IA - Entorno de Desarrollo Optimizado
:: ============================================

title ZEUS IA - Iniciando...

:: Configuración
SET BACKEND_TITLE=ZEUS IA Backend (FastAPI)
SET FRONTEND_TITLE=ZEUS IA Frontend (Vite)
SET BACKEND_URL=http://localhost:8000
SET FRONTEND_URL=http://localhost:5173
SET PYTHON_CMD=python
SET NPM_CMD=npm.cmd

:: Obtener ruta absoluta del directorio del proyecto
set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"

:: Limpiar pantalla
cls

:: Mostrar encabezado
echo.
echo  ===========================================
echo   ZEUS IA - Iniciando Entorno de Desarrollo
echo  ===========================================
echo.

:: Verificar si los directorios existen
if not exist "%BACKEND_DIR%" (
    echo [ERROR] No se encuentra el directorio 'backend'
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%" (
    echo [ERROR] No se encuentra el directorio 'frontend'
    pause
    exit /b 1
)

:: Verificar Python
where %PYTHON_CMD% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python no está instalado o no está en el PATH
    echo Por favor, instala Python 3.8 o superior desde https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Verificar Node.js
where %NPM_CMD% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js no está instalado o no está en el PATH
    echo Por favor, instala Node.js 16 o superior desde https://nodejs.org/
    pause
    exit /b 1
)

:: Verificar pip
%PYTHON_CMD% -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip no está instalado. Ejecuta: %PYTHON_CMD% -m ensurepip --upgrade
    pause
    exit /b 1
)

:: Configuración de Backend
cd /d "%BACKEND_DIR%"

:: Verificar/crear entorno virtual
if not exist "venv" (
    echo [CREANDO] Entorno virtual de Python...
    %PYTHON_CMD% -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] No se pudo crear el entorno virtual
        pause
        exit /b 1
    )
)

:: Activar entorno virtual e instalar dependencias
call "%BACKEND_DIR%\venv\Scripts\activate.bat"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se pudo activar el entorno virtual
    pause
    exit /b 1
)

echo [INSTALANDO] Dependencias de Python...
pip install -r requirements.txt >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Error instalando dependencias de Python
    pause
    exit /b 1
)

:: Iniciar Backend en una nueva ventana
echo.
echo [INICIANDO] %BACKEND_TITLE%

:: Crear un archivo temporal para iniciar el backend
echo @echo off > "%TEMP%\start_backend.bat"
echo title %BACKEND_TITLE% >> "%TEMP%\start_backend.bat"
echo cd /d "%BACKEND_DIR%" >> "%TEMP%\start_backend.bat"
echo call "%BACKEND_DIR%\venv\Scripts\activate.bat" >> "%TEMP%\start_backend.bat"
echo echo [BACKEND] Limpiando puerto 8000... >> "%TEMP%\start_backend.bat"
echo netstat -ano ^| findstr :8000 ^> "%TEMP%\ports8000.txt" >> "%TEMP%\start_backend.bat"
echo for /f "tokens=5" %%%%a in ("%TEMP%\ports8000.txt") do taskkill /PID %%%%a /F 2^>nul >> "%TEMP%\start_backend.bat"
echo del "%TEMP%\ports8000.txt" 2^>nul >> "%TEMP%\start_backend.bat"
echo timeout /t 2 ^>nul >> "%TEMP%\start_backend.bat"
echo echo [BACKEND] Iniciando servidor... >> "%TEMP%\start_backend.bat"
echo uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 >> "%TEMP%\start_backend.bat"
echo pause >> "%TEMP%\start_backend.bat"

start "%BACKEND_TITLE%" cmd /k ""%TEMP%\start_backend.bat""

echo [ESPERANDO] Iniciando backend (10 segundos)...
timeout /t 10 >nul

:: Iniciar frontend en una nueva ventana
echo.
echo [INICIANDO] %FRONTEND_TITLE%

:: Crear archivo temporal para iniciar el frontend
echo @echo off > "%TEMP%\start_frontend.bat"
echo title %FRONTEND_TITLE% >> "%TEMP%\start_frontend.bat"
echo cd /d "%FRONTEND_DIR%" >> "%TEMP%\start_frontend.bat"

echo echo [FRONTEND] Instalando dependencias... >> "%TEMP%\start_frontend.bat"
echo call %NPM_CMD% install --no-audit --no-fund --loglevel=error >> "%TEMP%\start_frontend.bat"
echo if errorlevel 1 goto error >> "%TEMP%\start_frontend.bat"

echo echo. >> "%TEMP%\start_frontend.bat"

echo echo [FRONTEND] Limpiando puerto 5173... >> "%TEMP%\start_frontend.bat"
echo netstat -ano ^| findstr :5173 ^> "%TEMP%\ports5173.txt" >> "%TEMP%\start_frontend.bat"
echo for /f "tokens=5" %%%%a in ("%TEMP%\ports5173.txt") do taskkill /PID %%%%a /F 2^>nul >> "%TEMP%\start_frontend.bat"
echo del "%TEMP%\ports5173.txt" 2^>nul >> "%TEMP%\start_frontend.bat"
echo timeout /t 2 ^>nul >> "%TEMP%\start_frontend.bat"
echo echo [FRONTEND] Iniciando servidor de desarrollo... >> "%TEMP%\start_frontend.bat"
echo call %NPM_CMD% run dev >> "%TEMP%\start_frontend.bat"
echo if errorlevel 1 goto error >> "%TEMP%\start_frontend.bat"

echo :error >> "%TEMP%\start_frontend.bat"
echo echo. >> "%TEMP%\start_frontend.bat"
echo echo [FRONTEND] El servidor se ha detenido. >> "%TEMP%\start_frontend.bat"
echo pause >> "%TEMP%\start_frontend.bat"

:: Iniciar frontend en nueva ventana
start "%FRONTEND_TITLE%" cmd /k ""%TEMP%\start_frontend.bat""

:: Esperar a que el backend esté completamente listo
echo.
echo Esperando a que el backend esté listo...
timeout /t 5 >nul

:: Verificar si el backend está en ejecución
echo.
echo [VERIFICANDO] Estado del backend...
timeout /t 5 >nul

:: Intentar acceder a la documentación
curl -s -o nul -w "%%{http_code}" "%BACKEND_URL%/api/docs" > "%TEMP%\http_status.txt"
set /p HTTP_STATUS= < "%TEMP%\http_status.txt"

if "!HTTP_STATUS!"=="200" (
    echo [ÉXITO] Backend funcionando correctamente
    
    :: Abrir documentación del backend y frontend
    echo.
    echo [ABRIENDO] Documentación y aplicación...
    
    start "" "%BACKEND_URL%/api/docs"
    timeout /t 2 >nul
    start "" "%BACKEND_URL%/api/redoc"
    timeout /t 2 >nul
    start "" "%FRONTEND_URL%"
    
    echo.
    echo Se han abierto las siguientes pestañas en tu navegador:
    echo 1. Swagger UI: %BACKEND_URL%/api/docs
    echo 2. ReDoc: %BACKEND_URL%/api/redoc
    echo 3. Frontend: %FRONTEND_URL%
) else (
    echo [ADVERTENCIA] No se pudo conectar con el backend (Código: !HTTP_STATUS!)
    echo Se intentará abrir la documentación de todos modos...
    
    start "" "%BACKEND_URL%/api/docs"
    timeout /t 1 >nul
    start "" "%BACKEND_URL%/api/redoc"
    start "" "%FRONTEND_URL%"
    
    echo.
    echo Se intentaron abrir las siguientes URLs:
    echo 1. Swagger UI: %BACKEND_URL%/api/docs
    echo 2. ReDoc: %BACKEND_URL%/api/redoc
    echo 3. Frontend: %FRONTEND_URL%
    echo.
    echo Si las páginas no se cargan, verifica que el backend se esté ejecutando correctamente.
)
echo.
echo Presiona cualquier tecla para detener los servicios...
pause >nul

echo.
echo [INFO] Stopping all services...
taskkill /FI "WINDOWTITLE eq %BACKEND_TITLE%" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq %FRONTEND_TITLE%" /F >nul 2>&1

echo [INFO] All services stopped.
timeout /t 2 >nul
exit /b 0
