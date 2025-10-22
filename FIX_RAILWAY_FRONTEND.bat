@echo off
REM ========================================
REM ZEUS-IA - Arreglar Railway Frontend
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Arreglando Railway Frontend
echo ========================================
echo.

echo [1] Yendo a carpeta frontend...
cd frontend
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se encontro la carpeta frontend
    pause
    exit /b 1
)

echo [2] Instalando dependencias...
npm install
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo la instalacion de dependencias
    pause
    exit /b 1
)

echo [3] Build para produccion...
npm run build
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo el build
    pause
    exit /b 1
)

echo [4] Copiando frontend a backend/static...
cd ..
if not exist backend\static mkdir backend\static
xcopy /E /I /Y frontend\dist\* backend\static\
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo la copia del frontend
    pause
    exit /b 1
)

echo [5] Commit y push para Railway...
git add backend/static/
git commit -m "Fix: Copy frontend to backend/static for Railway deployment"
git push origin main

echo.
echo ========================================
echo Frontend copiado a Railway!
echo ========================================
echo.
echo Railway auto-desplegara en 2-3 minutos
echo Verificar en: https://zeus-ia-production-16d8.up.railway.app/
echo.

pause

