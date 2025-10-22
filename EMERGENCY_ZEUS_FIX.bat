@echo off
REM ========================================
REM ZEUS-IA - Emergency Fix
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Emergency Fix
echo ========================================
echo.

echo [1] Railway con error 500 persistente...
echo.

echo [2] SOLUCIÓN ALTERNATIVA - Deploy Frontend Separado:
echo.
echo === OPCIÓN A - VERCEL ===
echo cd frontend
echo vercel --prod
echo.
echo Variables en Vercel:
echo VITE_API_URL=https://zeus-ia-production-16d8.up.railway.app/api/v1
echo VITE_WS_URL=wss://zeus-ia-production-16d8.up.railway.app/api/v1/ws
echo.

echo === OPCIÓN B - NETLIFY ===
echo cd frontend
echo netlify deploy --prod
echo.

echo === OPCIÓN C - RAILWAY FRONTEND SEPARADO ===
echo Crear nuevo servicio en Railway para frontend
echo.

echo [3] Mientras tanto - Usar Local:
echo.
echo cd frontend
echo npm run dev
echo.
echo Abrir: http://localhost:5173
echo.

echo [4] Configurar para Railway Backend:
echo.
echo En frontend/src/config.ts:
echo VITE_API_URL=https://zeus-ia-production-16d8.up.railway.app/api/v1
echo VITE_WS_URL=wss://zeus-ia-production-16d8.up.railway.app/api/v1/ws
echo.

echo ========================================
echo Emergency Fix completado
echo ========================================
echo.

pause
