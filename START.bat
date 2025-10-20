@echo off
title ZEUS-IA Iniciando...

echo.
echo ========================================
echo      ZEUS-IA - Iniciando Sistema
echo ========================================
echo.

:: Iniciar Backend
echo [1/2] Iniciando Backend...
start "ZEUS Backend" cmd /c "cd backend && python -m uvicorn app.main:app --reload --port 8000"
timeout /t 5 >nul
echo OK: Backend iniciado

:: Iniciar Frontend
echo [2/2] Iniciando Frontend...
start "ZEUS Frontend" cmd /c "cd frontend && npm run dev"
timeout /t 5 >nul
echo OK: Frontend iniciado

echo.
echo ========================================
echo        ZEUS-IA INICIADO
echo ========================================
echo.
echo Accede en: http://localhost:5173
echo API Docs:  http://localhost:8000/docs
echo.
echo Email:    marketingdigitalper.seo@gmail.com
echo Password: Carnay19
echo.
echo Para detener: STOP.bat
echo.

:: Abrir navegador
start http://localhost:5173

pause

