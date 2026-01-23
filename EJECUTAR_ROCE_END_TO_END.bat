@echo off
echo ========================================
echo ROCE - Real Operational Company Evaluation
echo Auditoria End-to-End para Empresa Real
echo ========================================
echo.

REM Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no está instalado o no está en el PATH
    pause
    exit /b 1
)

REM Verificar que el backend está ejecutándose
echo Verificando conexión con backend...
curl -s http://localhost:8000/api/v1/system/status >nul 2>&1
if errorlevel 1 (
    echo ADVERTENCIA: No se pudo conectar con el backend en http://localhost:8000
    echo Asegúrate de que el backend esté ejecutándose antes de continuar
    echo.
    set /p continue="¿Deseas continuar de todas formas? (S/N): "
    if /i not "%continue%"=="S" (
        exit /b 1
    )
)

echo.
echo Ejecutando auditoría ROCE...
echo.

python ROCE_END_TO_END_REAL_COMPANY.py http://localhost:8000

if errorlevel 1 (
    echo.
    echo ========================================
    echo AUDITORIA COMPLETADA CON ERRORES
    echo ========================================
    echo Revisa el reporte generado para más detalles
) else (
    echo.
    echo ========================================
    echo AUDITORIA COMPLETADA EXITOSAMENTE
    echo ========================================
)

echo.
pause
