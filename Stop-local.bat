@echo off
echo ========================================
echo    ZEUS-IA - Detener Aplicacion
echo ========================================
echo.

echo [1/2] Deteniendo Frontend (Vue.js)...
taskkill /F /IM node.exe 2>nul
echo ✓ Frontend detenido
echo.

echo [2/2] Deteniendo Backend (FastAPI)...
taskkill /F /IM python.exe 2>nul
echo ✓ Backend detenido
echo.

echo ========================================
echo    ¡ZEUS-IA detenido completamente!
echo ========================================
echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
