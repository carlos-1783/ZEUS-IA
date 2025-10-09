@echo off
echo Starting ZEUS-IA Backend...
echo %DATE% %TIME% > backend_error.log

cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not in your PATH. Please ensure Python is installed and added to your system PATH.
    echo Python is not in your PATH. Please ensure Python is installed and added to your system PATH. >> backend_error.log
    pause
    exit /b 1
)

:: Check if the backend directory exists
if not exist "backend\" (
    echo Backend directory not found. Please run this script from the project root directory.
    echo Backend directory not found. Please run this script from the project root directory. >> backend_error.log
    pause
    exit /b 1
)

:: Change to the backend directory and start the server
cd backend

echo Starting Uvicorn server...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-level debug >> ..\backend.log 2>&1

:: If we get here, the server has stopped
echo.
echo Uvicorn server has stopped. Check backend.log for details.
pause
