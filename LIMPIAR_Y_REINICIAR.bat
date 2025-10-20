@echo off
echo ========================================
echo    LIMPIANDO Y REINICIANDO ZEUS-IA
echo ========================================

echo [1/4] Matando procesos...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
taskkill /F /IM uvicorn.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Liberando puertos...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

echo [3/4] Limpiando cache...
if exist "frontend\node_modules\.vite" rmdir /s /q "frontend\node_modules\.vite" 2>nul
if exist "frontend\dist" rmdir /s /q "frontend\dist" 2>nul

echo [4/4] Iniciando servicios...
start "Backend" cmd /k "cd backend && python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0"
timeout /t 5 /nobreak >nul
start "Frontend" cmd /k "cd frontend && npm run dev"

echo ========================================
echo    ZEUS-IA REINICIADO
echo ========================================
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo IMPORTANTE: Usa modo incognito o limpia cache
echo.
echo Credenciales:
echo   Email:    marketingdigitalper.seo@gmail.com
echo   Password: Carnay19
echo ========================================

timeout /t 3 /nobreak >nul
start "" "http://localhost:5173/auth/login"
