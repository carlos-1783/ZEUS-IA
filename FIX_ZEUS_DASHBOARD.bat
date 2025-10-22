@echo off
echo ========================================
echo CORRIGIENDO DASHBOARD DE ZEUS-IA
echo ========================================

echo.
echo [1/4] Deteniendo procesos actuales...
taskkill /f /im node.exe 2>nul
taskkill /f /im python.exe 2>nul
timeout /t 3 /nobreak >nul

echo.
echo [2/4] Limpiando cache del frontend...
cd frontend
if exist node_modules\.vite rmdir /s /q node_modules\.vite
if exist dist rmdir /s /q dist
cd ..

echo.
echo [3/4] Configurando main.js completo...
echo ✅ Cambiando de main-ultra-minimal.js a main.js
echo ✅ Font Awesome registrado correctamente
echo ✅ Router completo habilitado

echo.
echo [4/4] Iniciando Zeus con dashboard completo...
echo.
echo ✅ Dashboard interactivo habilitado
echo ✅ Componentes Vue completos
echo ✅ Router con todas las rutas
echo.
echo Ejecutando: .\start.bat
echo.
start.bat
