@echo off
echo ============================================
echo   ZEUS IA - Limpieza de Puertos
echo ============================================
echo.

echo [INFO] Limpiando puerto 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo [INFO] Terminando proceso PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo [INFO] Limpiando puerto 5173 (Frontend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    echo [INFO] Terminando proceso PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo [INFO] Limpiando puerto 5174 (HMR)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174') do (
    echo [INFO] Terminando proceso PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo [INFO] Esperando 3 segundos para que los puertos se liberen...
timeout /t 3 >nul

echo [INFO] Verificando puertos libres...
netstat -ano | findstr ":8000 :5173 :5174" >nul
if %ERRORLEVEL% EQU 0 (
    echo [ADVERTENCIA] Algunos puertos aún están ocupados
) else (
    echo [ÉXITO] Todos los puertos están libres
)

echo.
echo [INFO] Limpieza completada
pause
