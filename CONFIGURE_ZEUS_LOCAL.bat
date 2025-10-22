@echo off
echo ========================================
echo CONFIGURANDO ZEUS-IA PARA DESARROLLO LOCAL
echo ========================================

echo.
echo [1/4] Configurando variables de entorno del frontend...
echo VITE_API_URL=http://localhost:8000/api/v1 > frontend\.env
echo VITE_WS_URL=ws://localhost:8000/api/v1/ws >> frontend\.env
echo VITE_APP_NAME=ZEUS-IA >> frontend\.env
echo VITE_APP_VERSION=1.0.0 >> frontend\.env
echo VITE_ENABLE_ANALYTICS=false >> frontend\.env

echo.
echo [2/4] Limpiando cache del frontend...
cd frontend
if exist node_modules\.vite rmdir /s /q node_modules\.vite
if exist dist rmdir /s /q dist
cd ..

echo.
echo [3/4] Verificando configuración del backend...
echo SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b6895b8c4d2f1a6e7b9c8d5e4f3a2b1c0 > backend\.env
echo REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c >> backend\.env
echo ACCESS_TOKEN_EXPIRE_MINUTES=30 >> backend\.env
echo REFRESH_TOKEN_EXPIRE_DAYS=7 >> backend\.env

echo.
echo [4/4] Configuración completada!
echo.
echo ✅ Variables de entorno configuradas
echo ✅ Cache limpiado
echo ✅ Backend configurado
echo.
echo Para iniciar Zeus:
echo   1. Ejecutar: .\start.bat
echo   2. Abrir: http://localhost:5173
echo   3. Login: marketingdigitalper.seo@gmail.com / Carnay19
echo.
pause
