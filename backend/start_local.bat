@echo off
echo ========================================
echo ZEUS-IA Backend - Inicio Local
echo ========================================
echo.

REM Activar entorno virtual si existe
if exist venv\Scripts\activate.bat (
    echo [1/3] Activando entorno virtual...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] Entorno virtual no encontrado. Creando...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [1/3] Instalando dependencias...
    pip install -r requirements.txt
)

echo.
echo [2/3] Verificando base de datos...
if not exist zeus.db (
    echo Base de datos no existe, se creará automáticamente...
)

echo.
echo [3/3] Iniciando servidor backend...
echo Backend disponible en: http://localhost:8000
echo API disponible en: http://localhost:8000/api/v1
echo.
echo Presiona CTRL+C para detener el servidor
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause

