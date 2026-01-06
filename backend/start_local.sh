#!/bin/bash

echo "========================================"
echo "ZEUS-IA Backend - Inicio Local"
echo "========================================"
echo ""

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    echo "[1/3] Activando entorno virtual..."
    source venv/bin/activate
else
    echo "[WARNING] Entorno virtual no encontrado. Creando..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[1/3] Instalando dependencias..."
    pip install -r requirements.txt
fi

echo ""
echo "[2/3] Verificando base de datos..."
if [ ! -f "zeus.db" ]; then
    echo "Base de datos no existe, se creará automáticamente..."
fi

echo ""
echo "[3/3] Iniciando servidor backend..."
echo "Backend disponible en: http://localhost:8000"
echo "API disponible en: http://localhost:8000/api/v1"
echo ""
echo "Presiona CTRL+C para detener el servidor"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

