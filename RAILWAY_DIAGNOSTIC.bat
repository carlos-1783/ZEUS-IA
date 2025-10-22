@echo off
REM ========================================
REM ZEUS-IA - Diagnóstico Railway DevOps
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Diagnóstico Railway DevOps
echo ========================================
echo.

echo [1] Verificando variables de entorno Railway...
echo.
echo Variables requeridas:
echo.
echo === BACKEND ===
echo BACKEND_URL=https://zeus-ia-production-16d8.up.railway.app
echo PORT=8000
echo DATABASE_URL=sqlite:///./zeus.db
echo.
echo === JWT ===
echo SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b1cb7ddc2071ad633aee3c8568d62b13b
echo REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c92189f25be3acd36ad07096d
echo ACCESS_TOKEN_EXPIRE_MINUTES=30
echo REFRESH_TOKEN_EXPIRE_DAYS=7
echo.
echo === CORS ===
echo BACKEND_CORS_ORIGINS=https://zeus-ia-production-16d8.up.railway.app,http://localhost:5173
echo.
echo === FRONTEND ===
echo VITE_API_URL=https://zeus-ia-production-16d8.up.railway.app/api/v1
echo VITE_WS_URL=wss://zeus-ia-production-16d8.up.railway.app/api/v1/ws
echo.

echo [2] Verificando endpoints críticos...
echo.
echo Endpoints a verificar:
echo - GET /health
echo - GET /api/v1/auth/me
echo - POST /api/v1/auth/login
echo - WebSocket /api/v1/ws/{client_id}
echo.

echo [3] Comandos de verificación...
echo.
echo curl https://zeus-ia-production-16d8.up.railway.app/health
echo curl -X POST https://zeus-ia-production-16d8.up.railway.app/api/v1/auth/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=marketingdigitalper.seo@gmail.com&password=Carnay19"
echo.

echo ========================================
echo Diagnóstico completado
echo ========================================
echo.

pause
