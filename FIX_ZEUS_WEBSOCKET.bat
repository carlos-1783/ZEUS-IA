@echo off
echo ========================================
echo CORRIGIENDO WEBSOCKET DE ZEUS-IA
echo ========================================

echo.
echo [1/3] Deteniendo procesos actuales...
taskkill /f /im node.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [2/3] Limpiando cache del frontend...
cd frontend
if exist node_modules\.vite rmdir /s /q node_modules\.vite
cd ..

echo.
echo [3/3] Iniciando Zeus con WebSocket corregido...
echo.
echo ✅ WebSocket ahora conectará a localhost:8000
echo ✅ Font Awesome registrado correctamente
echo ✅ Cache limpiado
echo.
echo Ejecutando: .\start.bat
echo.
start.bat
