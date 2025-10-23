@echo off
echo ========================================
echo REBUILD FRONTEND PARA RAILWAY
echo ========================================
echo.

cd frontend

echo [1/4] Limpiando cache y node_modules...
if exist node_modules rmdir /s /q node_modules
if exist dist rmdir /s /q dist
if exist node_modules\.vite rmdir /s /q node_modules\.vite

echo.
echo [2/4] Instalando dependencias...
call npm install

echo.
echo [3/4] Verificando vite.config.ts...
findstr /C:"base = '/'" vite.config.ts
if errorlevel 1 (
    echo ERROR: base no está configurado correctamente
    exit /b 1
) else (
    echo ✅ base: '/' configurado correctamente
)

echo.
echo [4/4] Construyendo frontend con configuración de producción...
set NODE_ENV=production
call npm run build

echo.
echo [5/6] Copiando build al backend...
cd ..
if exist backend\static rmdir /s /q backend\static
xcopy /E /I /Y frontend\dist backend\static

echo.
echo ========================================
echo ✅ BUILD COMPLETADO
echo ========================================
echo.
echo Archivos generados en:
echo - frontend\dist
echo - backend\static
echo.
echo SIGUIENTE PASO:
echo 1. Verifica que backend\static\index.html tenga rutas como /assets/js/...
echo 2. Commitea los cambios
echo 3. Push a Railway
echo.
pause

