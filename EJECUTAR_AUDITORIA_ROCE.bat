@echo off
echo ========================================
echo    AUDITORIA ROCE END-TO-END - ZEUS-IA
echo ========================================
echo.

echo [1/3] Verificando que el backend este ejecutandose...
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Backend no esta ejecutandose en http://localhost:8000
    echo.
    echo Por favor, inicia el backend primero:
    echo    cd backend
    echo    python -m uvicorn app.main:app --reload --port 8000
    echo.
    pause
    exit /b 1
)
echo ✅ Backend esta ejecutandose
echo.

echo [2/3] Instalando dependencias de Python si es necesario...
pip install requests >nul 2>&1
echo ✅ Dependencias verificadas
echo.

echo [3/3] Ejecutando auditoria ROCE End-to-End...
echo.
python AUDITORIA_ROCE_END_TO_END.py

echo.
echo ========================================
echo    AUDITORIA COMPLETADA
echo ========================================
echo.
echo Revisa el archivo AUDITORIA_ROCE_REPORT_*.json para el reporte completo
echo.
pause
