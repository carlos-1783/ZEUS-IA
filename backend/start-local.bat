@echo off
echo ========================================
echo Iniciando ZEUS-IA Backend Local
echo ========================================
echo.

cd /d "%~dp0"

echo Verificando Python...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python no encontrado. Por favor instala Python 3.10 o superior.
    pause
    exit /b 1
)

echo.
echo Verificando dependencias...
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
)

echo Activando entorno virtual...
call venv\Scripts\activate.bat

echo Instalando/actualizando dependencias...
pip install -q -r requirements.txt

echo.
echo ========================================
echo Iniciando servidor en http://localhost:8000
echo Presiona Ctrl+C para detener
echo ========================================
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause

