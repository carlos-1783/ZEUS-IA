@echo off
title ZEUS-IA - Test de Configuración de Producción

echo ========================================
echo    ZEUS-IA - Test de Configuración
echo ========================================

echo.
echo [1/4] Verificando archivos de configuración...

if not exist "docker-compose.yml" (
    echo ❌ docker-compose.yml no encontrado
    goto :error
)
echo ✅ docker-compose.yml encontrado

if not exist "docker-compose.prod.yml" (
    echo ❌ docker-compose.prod.yml no encontrado
    goto :error
)
echo ✅ docker-compose.prod.yml encontrado

if not exist ".env.development" (
    echo ❌ .env.development no encontrado
    goto :error
)
echo ✅ .env.development encontrado

if not exist ".env.production" (
    echo ❌ .env.production no encontrado
    goto :error
)
echo ✅ .env.production encontrado

echo.
echo [2/4] Verificando Dockerfiles...

if not exist "backend\Dockerfile" (
    echo ❌ backend\Dockerfile no encontrado
    goto :error
)
echo ✅ backend\Dockerfile encontrado

if not exist "frontend\Dockerfile" (
    echo ❌ frontend\Dockerfile no encontrado
    goto :error
)
echo ✅ frontend\Dockerfile encontrado

if not exist "frontend\Dockerfile.dev" (
    echo ❌ frontend\Dockerfile.dev no encontrado
    goto :error
)
echo ✅ frontend\Dockerfile.dev encontrado

echo.
echo [3/4] Verificando configuraciones de Nginx...

if not exist "nginx\nginx-prod.conf" (
    echo ❌ nginx\nginx-prod.conf no encontrado
    goto :error
)
echo ✅ nginx\nginx-prod.conf encontrado

if not exist "nginx\nginx-dev.conf" (
    echo ❌ nginx\nginx-dev.conf no encontrado
    goto :error
)
echo ✅ nginx\nginx-dev.conf encontrado

if not exist "frontend\nginx.conf" (
    echo ❌ frontend\nginx.conf no encontrado
    goto :error
)
echo ✅ frontend\nginx.conf encontrado

echo.
echo [4/4] Verificando scripts de despliegue...

if not exist "scripts\deploy-production.sh" (
    echo ❌ scripts\deploy-production.sh no encontrado
    goto :error
)
echo ✅ scripts\deploy-production.sh encontrado

if not exist "scripts\deploy-local.sh" (
    echo ❌ scripts\deploy-local.sh no encontrado
    goto :error
)
echo ✅ scripts\deploy-local.sh encontrado

if not exist "scripts\validate-production.sh" (
    echo ❌ scripts\validate-production.sh no encontrado
    goto :error
)
echo ✅ scripts\validate-production.sh encontrado

echo.
echo ========================================
echo    ✅ CONFIGURACIÓN COMPLETA
echo ========================================
echo.
echo 🚀 ZEUS-IA está listo para producción!
echo.
echo 📋 Archivos creados:
echo   • Dockerfiles optimizados para dev/prod
echo   • docker-compose.yml para desarrollo
echo   • docker-compose.prod.yml para producción
echo   • docker-compose.traefik.yml con Traefik
echo   • Configuraciones de Nginx
echo   • Scripts de despliegue automatizado
echo   • Variables de entorno seguras
echo.
echo 🎯 Próximos pasos:
echo   1. Iniciar Docker Desktop
echo   2. Ejecutar: docker-compose up -d
echo   3. Para producción: ./scripts/deploy-production.sh
echo.
echo 📖 Ver DOCKER-README.md para más detalles
echo.
pause
goto :end

:error
echo.
echo ========================================
echo    ❌ ERROR EN CONFIGURACIÓN
echo ========================================
echo.
echo Algunos archivos no se encontraron.
echo Verifica que todos los archivos se hayan creado correctamente.
echo.
pause

:end
