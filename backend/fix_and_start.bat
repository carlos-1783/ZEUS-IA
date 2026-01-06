@echo off
echo ========================================
echo ZEUS-IA Backend - Fix y Reinicio
echo ========================================
echo.

REM Matar procesos en puerto 8000
echo [1/4] Verificando puerto 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Matando proceso %%a en puerto 8000...
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

REM Activar entorno virtual
echo [2/4] Activando entorno virtual...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Entorno virtual no encontrado en venv\
    echo Ejecuta primero: python -m venv venv
    pause
    exit /b 1
)

REM Ejecutar migración manualmente si es necesario
echo [3/4] Verificando migración de base de datos...
python -c "from app.db.base import _migrate_firewall_columns; from app.core.config import settings; _migrate_firewall_columns()" 2>&1

echo.
echo [4/4] Iniciando servidor backend...
echo.
echo ========================================
echo Backend disponible en: http://localhost:8000
echo API disponible en: http://localhost:8000/api/v1
echo Health check: http://localhost:8000/health
echo ========================================
echo.
echo Presiona CTRL+C para detener el servidor
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause

