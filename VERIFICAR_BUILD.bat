@echo off
echo ========================================
echo VERIFICAR BUILD DEL FRONTEND
echo ========================================
echo.

echo Verificando vite.config.ts...
findstr /C:"base = '/'" frontend\vite.config.ts
echo.

echo Verificando index.html generado...
if exist backend\static\index.html (
    echo ✅ backend\static\index.html existe
    echo.
    echo Contenido de las rutas de assets:
    findstr /C:"src=" backend\static\index.html
    findstr /C:"href=" backend\static\index.html
    echo.
    
    echo Verificando que las rutas sean relativas a la raíz (deben empezar con /assets/):
    findstr /C:"/assets/" backend\static\index.html
    if errorlevel 1 (
        echo ❌ ERROR: Las rutas NO son relativas a la raíz
        echo Las rutas deben ser /assets/js/... y /assets/css/...
    ) else (
        echo ✅ Las rutas son correctas (relativas a la raíz)
    )
) else (
    echo ❌ backend\static\index.html NO existe
    echo Ejecuta REBUILD_FRONTEND_RAILWAY.bat primero
)

echo.
echo ========================================
pause

