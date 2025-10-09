@echo off
echo Starting ZEUS-IA Backend in debug mode...
cd /d "%~dp0"

:: Check if Python is available
python --version
if %ERRORLEVEL% NEQ 0 (
    echo Python is not in your PATH. Please ensure Python is installed and added to your system PATH.
    pause
    exit /b 1
)

:: Check if the backend directory exists
if not exist "backend\" (
    echo Backend directory not found. Please run this script from the project root directory.
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Installing Python dependencies...
pip install -r backend/requirements.txt

:: Change to the backend directory and start the server with Python directly
echo Starting Uvicorn server...
cd backend
python -c "
import uvicorn
import sys
import traceback

try:
    print('Starting ZEUS-IA Backend...')
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=8001,
        reload=True,
        log_level='debug',
        workers=1
    )
except Exception as e:
    print(f'Error starting server: {e}')
    print('\nTraceback:')
    traceback.print_exc()
    input('\nPress Enter to exit...')
"

:: If we get here, the server has stopped
echo.
echo Uvicorn server has stopped.
pause
