@echo off
echo ========================================
echo DEPLOYMENT COMPLETO A RAILWAY
echo ========================================
echo.

echo [PASO 1] Verificando configuración...
call VERIFICAR_BUILD.bat
if errorlevel 1 (
    echo.
    echo ❌ La verificación falló. Construyendo frontend...
    call REBUILD_FRONTEND_RAILWAY.bat
)

echo.
echo [PASO 2] Agregando cambios a git...
git add .

echo.
echo [PASO 3] Creando commit...
git commit -m "fix: actualizar build del frontend con base: '/' para Railway"

echo.
echo [PASO 4] Pusheando a Railway...
echo ⚠️ ASEGÚRATE DE QUE ESTÁS EN LA RAMA CORRECTA
git branch
echo.
set /p continuar="¿Continuar con el push? (s/n): "
if /i "%continuar%"=="s" (
    git push
    echo.
    echo ========================================
    echo ✅ DEPLOYMENT INICIADO
    echo ========================================
    echo.
    echo Railway detectará los cambios y redesplegará automáticamente.
    echo Monitorea el despliegue en: https://railway.app/dashboard
) else (
    echo.
    echo Deployment cancelado.
)

echo.
pause

