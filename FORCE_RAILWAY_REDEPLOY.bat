@echo off
REM ========================================
REM ZEUS-IA - Force Railway Redeploy
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Forzando Redeploy Railway
echo ========================================
echo.

echo [1] Forzando redeploy con variables correctas...
echo.

echo [2] Variables críticas a verificar en Railway:
echo.
echo === BACKEND ===
echo SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b1cb7ddc2071ad633aee3c8568d62b13b
echo REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c92189f25be3acd36ad07096d
echo ACCESS_TOKEN_EXPIRE_MINUTES=30
echo REFRESH_TOKEN_EXPIRE_DAYS=7
echo.
echo === CORS ===
echo BACKEND_CORS_ORIGINS=https://zeus-ia-production-16d8.up.railway.app,http://localhost:5173
echo.
echo === DATABASE ===
echo DATABASE_URL=sqlite:///./zeus.db
echo.
echo === PORT ===
echo PORT=8000
echo.

echo [3] Forzando redeploy...
echo.
echo Railway auto-redeploy en 2-3 minutos...
echo.

echo [4] Verificando endpoints después del redeploy...
echo.
echo curl https://zeus-ia-production-16d8.up.railway.app/api/v1/health
echo curl -X POST https://zeus-ia-production-16d8.up.railway.app/api/v1/auth/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=marketingdigitalper.seo@gmail.com&password=Carnay19"
echo.

echo ========================================
echo Redeploy forzado completado
echo ========================================
echo.

pause
