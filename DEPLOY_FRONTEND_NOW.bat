@echo off
REM ========================================
REM ZEUS-IA - Deploy Frontend AHORA
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Deploy Frontend URGENTE
echo ========================================
echo.

echo [1] Verificando Vercel CLI...
where vercel >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Vercel CLI no esta instalado
    echo.
    echo Instalando Vercel CLI...
    npm install -g vercel
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: No se pudo instalar Vercel CLI
        echo.
        echo OPCION MANUAL:
        echo 1. Ir a: https://vercel.com/dashboard
        echo 2. Click "New Project"
        echo 3. Conectar GitHub repo
        echo 4. Seleccionar carpeta frontend
        echo 5. Deploy
        pause
        exit /b 1
    )
)

echo [OK] Vercel CLI encontrado
echo.

echo [2] Yendo a carpeta frontend...
cd frontend
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se encontro la carpeta frontend
    pause
    exit /b 1
)

echo [3] Instalando dependencias...
npm install
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo la instalacion de dependencias
    pause
    exit /b 1
)

echo [4] Build para produccion...
npm run build
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo el build
    pause
    exit /b 1
)

echo [5] Deploy en Vercel...
vercel --prod
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo el deploy en Vercel
    echo.
    echo OPCION MANUAL:
    echo 1. Ir a: https://vercel.com/dashboard
    echo 2. Click "New Project"
    echo 3. Conectar GitHub repo
    echo 4. Seleccionar carpeta frontend
    echo 5. Deploy
    pause
    exit /b 1
)

echo.
echo ========================================
echo Frontend desplegado exitosamente!
echo ========================================
echo.
echo IMPORTANTE: Configurar variables en Vercel:
echo VITE_API_URL=https://zeus-ia-production-16d8.up.railway.app/api/v1
echo VITE_WS_URL=wss://zeus-ia-production-16d8.up.railway.app/api/v1/ws
echo.

pause

