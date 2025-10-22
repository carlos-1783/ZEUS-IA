@echo off
echo ========================================
echo REINICIANDO ZEUS-IA COMPLETAMENTE
echo ========================================

echo.
echo [1/6] Deteniendo todos los procesos...
taskkill /f /im python.exe 2>nul
taskkill /f /im python3.exe 2>nul
taskkill /f /im python3.10.exe 2>nul
taskkill /f /im node.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [2/6] Limpiando cache del frontend...
cd frontend
if exist node_modules\.vite rmdir /s /q node_modules\.vite
if exist dist rmdir /s /q dist
if exist .env del .env
cd ..

echo.
echo [3/6] Configurando variables de entorno...
echo VITE_API_URL=http://localhost:8000/api/v1 > frontend\.env
echo VITE_WS_URL=ws://localhost:8000/api/v1/ws >> frontend\.env
echo VITE_APP_NAME=ZEUS-IA >> frontend\.env
echo VITE_APP_VERSION=1.0.0 >> frontend\.env
echo VITE_ENABLE_ANALYTICS=false >> frontend\.env

echo.
echo [4/6] Configurando backend...
echo SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b6895b8c4d2f1a6e7b9c8d5e4f3a2b1c0 > backend\.env
echo REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c >> backend\.env
echo ACCESS_TOKEN_EXPIRE_MINUTES=30 >> backend\.env
echo REFRESH_TOKEN_EXPIRE_DAYS=7 >> backend\.env

echo.
echo [5/6] Limpiando localStorage del navegador...
echo Abre las DevTools (F12) y ejecuta:
echo localStorage.clear();
echo sessionStorage.clear();
echo.

echo.
echo [6/6] Iniciando Zeus...
echo.
echo ✅ Configuración completada
echo ✅ Procesos detenidos
echo ✅ Cache limpiado
echo ✅ Variables configuradas
echo.
echo Ahora ejecuta: .\start.bat
echo.
pause
