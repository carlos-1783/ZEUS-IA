@echo off
:: =============================================
:: ZEUS-IA Startup Script (Optimized)
:: Version: 2.1
:: Description: Unified startup script for ZEUS-IA backend and frontend
:: Last Updated: 2025-07-11
:: =============================================

:: 1. Configuration
:: =============================================
setlocal enabledelayedexpansion
set "TITLE=ZEUS-IA Launcher"
title %TITLE%

:: Ports configuration
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

:: Paths
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%.."
set "FRONTEND_DIR=%PROJECT_DIR%..\frontend"
set "LOG_DIR=%BACKEND_DIR%\logs"
set "BACKEND_LOG=%LOG_DIR%\backend.log"
set "FRONTEND_LOG=%LOG_DIR%\frontend.log"

:: Ensure logs directory exists
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    if !errorlevel! neq 0 (
        echo %RED%[ERROR] Failed to create log directory: %LOG_DIR%%RESET%
        pause
        exit /b 1
    )
)

:: Colors
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "RESET=[0m"

:: 2. Initialization
:: =============================================
:init
cls
echo %BLUE%=== %TITLE% ===%RESET%
echo.

:: Skip admin rights check for development
echo %YELLOW%[INFO] Running in developer mode (admin rights not required)%RESET%

:: Create logs directory if it doesn't exist
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: 3. Cleanup function
:: =============================================
:cleanup
echo %YELLOW%[INFO] Cleaning up existing processes...%RESET%
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 >nul

:: 4. Start Backend
:: =============================================
:start_backend
echo.
echo %BLUE%[1/2] Starting Backend...%RESET%

if not exist "%BACKEND_DIR%\" (
    echo %RED%[ERROR] Backend directory not found at %BACKEND_DIR%%RESET%
    pause
    exit /b 1
)

cd /d "%BACKEND_DIR%"

:: Check Python installation
where python >nul 2>&1
if !errorlevel! neq 0 (
    echo %RED%[ERROR] Python is not installed or not in PATH%RESET%
    pause
    exit /b 1
)

:: Create/activate virtual environment
if not exist "%BACKEND_DIR%\venv\" (
    echo %YELLOW%[INFO] Creating Python virtual environment...%RESET%
    python -m venv "%BACKEND_DIR%\venv"
    if !errorlevel! neq 0 (
        echo %RED%[ERROR] Failed to create virtual environment%RESET%
        pause
        exit /b 1
    )
)

:: Install/update dependencies
echo %YELLOW%[INFO] Installing/updating Python dependencies...%RESET%
call "%BACKEND_DIR%\venv\Scripts\pip" install --upgrade pip
if !errorlevel! neq 0 (
    echo %RED%[ERROR] Failed to upgrade pip%RESET%
    pause
    exit /b 1
)

call "%BACKEND_DIR%\venv\Scripts\pip" install -r "%BACKEND_DIR%\requirements.txt"
if !errorlevel! neq 0 (
    echo %RED%[ERROR] Failed to install Python dependencies%RESET%
    echo %YELLOW%[INFO] Attempting to continue with existing packages...%RESET%
    timeout /t 2 >nul
)

:: Check if port is available
netstat -ano | find ":%BACKEND_PORT%" | find "LISTENING" >nul
if !errorlevel! equ 0 (
    echo %YELLOW%[WARNING] Port %BACKEND_PORT% is already in use. Trying to find an available port...%RESET%
    set /a "BACKEND_PORT=%BACKEND_PORT% + 1"
    goto :check_port_again
)

:port_available
echo %GREEN%[OK] Starting backend on http://localhost:%BACKEND_PORT%%RESET%

:: Create a temporary batch file to run the backend
set "BACKEND_BAT=%TEMP%\zeus_backend_%RANDOM%.bat"

echo @echo off > "%BACKEND_BAT%"
echo title ZEUS-IA Backend >> "%BACKEND_BAT%"
echo echo [%%TIME%%] Starting ZEUS-IA Backend... >> "%BACKEND_BAT%"
echo echo Backend URL: http://localhost:%BACKEND_PORT% >> "%BACKEND_BAT%"
echo echo API Docs:    http://localhost:%BACKEND_PORT%/docs >> "%BACKEND_LOG%"
echo echo Log file:   %BACKEND_LOG% >> "%BACKEND_BAT%"
echo cd /d "%BACKEND_DIR%" >> "%BACKEND_BAT%"
echo call "%BACKEND_DIR%\venv\Scripts\activate" >> "%BACKEND_BAT%"
echo python -m uvicorn app.main:app --reload --host 0.0.0.0 --port %BACKEND_PORT% >> "%BACKEND_BAT%"
echo if %%ERRORLEVEL%% NEQ 0 ( >> "%BACKEND_BAT%"
echo   echo. >> "%BACKEND_BAT%"
echo   echo [ERROR] Backend failed to start >> "%BACKEND_BAT%"
echo   echo Check the log file for details: %BACKEND_LOG% >> "%BACKEND_BAT%"
echo   pause >> "%BACKEND_BAT%"
echo   exit /b 1 >> "%BACKEND_BAT%"
echo ) >> "%BACKEND_BAT%"

if not exist "%BACKEND_BAT%" (
    echo %RED%[ERROR] Failed to create backend startup script%RESET%
    pause
    exit /b 1
)

:: Start the backend process
start "ZEUS-IA Backend" cmd /k ""%BACKEND_BAT%" ^> "%BACKEND_LOG%" 2^>^&1 ^&^& (echo. ^&^& echo %GREEN%Backend is running at http://localhost:%BACKEND_PORT%%RESET% ^&^& echo %GREEN%API Documentation: http://localhost:%BACKEND_PORT%/docs%RESET% ^&^& echo.) ^|^| (echo. ^&^& echo %RED%Backend failed to start. Check %BACKEND_LOG% for details.%RESET% ^&^& pause ^&^& exit /b 1) ^&^& del "%BACKEND_BAT%" ^&^& pause ^&^& exit

:: 5. Start Frontend
:: =============================================
:start_frontend
echo.
echo %BLUE%[2/2] Starting Frontend...%RESET%

if not exist "%FRONTEND_DIR%\" (
    echo %RED%[ERROR] Frontend directory not found at %FRONTEND_DIR%%RESET%
    pause
    exit /b 1
)

cd /d "%FRONTEND_DIR%"

:: Install dependencies if needed
if not exist "node_modules\" (
    echo %YELLOW%[INFO] Installing Node.js dependencies...%RESET%
    call npm install
    if !errorlevel! neq 0 (
        echo %RED%[ERROR] Failed to install Node.js dependencies%RESET%
        pause
        exit /b 1
    )
)

:: Start frontend in a new window
echo %GREEN%[OK] Starting frontend on http://localhost:%FRONTEND_PORT%%RESET%

:: Create a temporary batch file to run the frontend
(
  echo @echo off
  echo title ZEUS-IA Frontend
  echo echo [%TIME%] Starting ZEUS-IA Frontend...
  echo echo Log file: %FRONTEND_LOG%
  echo cd /d "%FRONTEND_DIR%"
  echo call npm run dev
) > "%TEMP%\start_frontend.bat"

:: Start the frontend process
start "ZEUS-IA Frontend" cmd /k ""%TEMP%\start_frontend.bat" ^> "%FRONTEND_LOG%" 2^>^&1 ^&^& (echo. ^&^& echo %GREEN%Frontend is running at http://localhost:%FRONTEND_PORT%%RESET% ^&^& echo.) ^|^| (echo. ^&^& echo %RED%Frontend failed to start. Check %FRONTEND_LOG% for details.%RESET% ^&^& pause ^&^& exit /b 1) ^&^& pause ^&^& exit

:: 6. Final Setup
:: =============================================
:final_setup
echo.
echo %GREEN%=== ZEUS-IA STARTED SUCCESSFULLY ===%RESET%
echo.
echo %BLUE%Frontend:%RESET%     http://localhost:%FRONTEND_PORT%
echo %BLUE%Backend API:%RESET%  http://localhost:%BACKEND_PORT%
echo %BLUE%API Docs:%RESET%     http://localhost:%BACKEND_PORT%/docs
echo %BLUE%ReDoc:%RESET%        http://localhost:%BACKEND_PORT%/redoc
echo %BLUE%Logs:%RESET%         %LOG_DIR%\
echo.

echo %YELLOW%[TIPS]%RESET%
echo - Si el navegador no se abre automáticamente, copia y pega las URLs anteriores.
echo - Para detener la aplicación, cierra las ventanas de consola del backend y frontend.
echo - Los logs detallados están disponibles en el directorio de logs.
echo.

:: Wait for servers to start
echo %YELLOW%[INFO] Waiting for servers to initialize...%RESET%
timeout /t 5 >nul

:: Open browser
start "" "http://localhost:%FRONTEND_PORT%"

echo %GREEN%Ready! The application should open in your browser shortly.%RESET%
echo If it doesn't open automatically, please visit:
echo http://localhost:%FRONTEND_PORT%
echo.

:: Keep the window open
pause
exit /b 0