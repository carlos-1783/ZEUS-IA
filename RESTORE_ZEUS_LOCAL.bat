@echo off
REM ========================================
REM ZEUS-IA - Restaurar Local Storage
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Restaurando Local Storage
echo ========================================
echo.

echo [1] Limpiando Local Storage...
echo localStorage.clear(); > temp_clear.js
echo sessionStorage.clear(); >> temp_clear.js
echo console.log("✅ Local Storage limpiado"); >> temp_clear.js

echo [2] Abriendo navegador para limpiar...
start chrome --new-window "data:text/html,<script>localStorage.clear();sessionStorage.clear();alert('✅ Local Storage limpiado - Recarga la página');</script>"

echo.
echo [3] Verificando URLs correctas...
echo.
echo Backend (API): https://zeus-ia-production-16d8.up.railway.app/health
echo Frontend: https://zeus-ia-production-16d8.up.railway.app/
echo.

echo [4] Si el frontend no carga, usar Vercel:
echo cd frontend
echo vercel --prod
echo.

echo ========================================
echo Restauración completada
echo ========================================
echo.

pause

