@echo off
echo ========================================
echo    ZEUS-IA - Ejecutar Localmente
echo ========================================
echo.

echo [1/5] Verificando que no hay procesos ejecutandose...
taskkill /F /IM node.exe 2>nul
taskkill /F /IM python.exe 2>nul
echo ✓ Procesos anteriores terminados
echo.

echo [2/5] Verificando que los puertos estan libres...
netstat -ano | findstr :8000 >nul
if %errorlevel% == 0 (
    echo ⚠️  Puerto 8000 ocupado, liberando...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %%a 2>nul
)
netstat -ano | findstr :5173 >nul
if %errorlevel% == 0 (
    echo ⚠️  Puerto 5173 ocupado, liberando...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %%a 2>nul
)
echo ✓ Puertos liberados
echo.

echo [3/5] Iniciando Backend (FastAPI)...
cd backend
start "ZEUS-IA Backend" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ✓ Backend iniciado en puerto 8000
echo.

echo [4/5] Esperando 8 segundos para que el backend se inicie completamente...
timeout /t 8 /nobreak >nul

echo [5/5] Iniciando Frontend (Vue.js)...
cd ..\frontend
start "ZEUS-IA Frontend" cmd /k "npm run dev"
echo ✓ Frontend iniciado en puerto 5173
echo.

echo ========================================
echo    ¡ZEUS-IA ejecutandose localmente!
echo ========================================
echo.
echo 🌐 Frontend: http://localhost:5173
echo 🔗 Backend:  http://localhost:8000
echo 📊 API Docs: http://localhost:8000/docs
echo 📖 ReDoc:    http://localhost:8000/redoc
echo.
echo ⏳ Esperando 10 segundos para que todo se inicie...
timeout /t 10 /nobreak >nul

echo.
echo 🚀 Abriendo aplicacion en el navegador...
start "" "http://localhost:5173"
echo.
echo ✅ ZEUS-IA esta listo para usar!
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul