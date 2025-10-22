@echo off
REM ========================================
REM ZEUS-IA - Configure Railway Variables
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Configurando Railway
echo ========================================
echo.

echo [1] Verificando Railway CLI...
where railway >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Railway CLI no esta instalado
    echo.
    echo Instalalo con: npm install -g @railway/cli
    echo O configura manualmente en: https://railway.app/dashboard
    pause
    exit /b 1
)

echo [OK] Railway CLI encontrado
echo.

echo [2] Configurando variables de entorno...
railway variables set SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b1cb7ddc2071ad633aee3c8568d62b13b
railway variables set REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c92189f25be3acd36ad07096d
railway variables set ACCESS_TOKEN_EXPIRE_MINUTES=30
railway variables set REFRESH_TOKEN_EXPIRE_DAYS=7
railway variables set JWT_ISSUER=zeus-ia-backend
railway variables set DEBUG=False
railway variables set ENVIRONMENT=production
railway variables set BACKEND_CORS_ORIGINS=https://zeus-ia-frontend-production.vercel.app,https://zeus-ia-production-16d8.up.railway.app

echo.
echo [3] Reiniciando servicio...
railway restart

echo.
echo ========================================
echo Variables configuradas exitosamente!
echo ========================================
echo.
echo Espera 2-3 minutos para que Railway se redespliegue
echo Luego:
echo 1. Abre el frontend
echo 2. Haz logout/login
echo 3. Verifica que WebSocket funciona
echo.

pause

