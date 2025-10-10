#!/bin/bash
set -e

echo "🚀 Iniciando ZEUS-IA Backend..."
echo "📍 Directorio actual: $(pwd)"
echo "📁 Contenido del directorio:"
ls -la

echo ""
echo "🔍 Verificando variables de entorno..."
echo "ENVIRONMENT: ${ENVIRONMENT:-not set}"
echo "DEBUG: ${DEBUG:-not set}"
echo "DATABASE_URL: ${DATABASE_URL:0:20}..." # Solo primeros 20 caracteres por seguridad

echo ""
echo "🐍 Versión de Python:"
python --version

echo ""
echo "📦 Paquetes instalados:"
pip list | grep -E "(fastapi|uvicorn|gunicorn|sqlalchemy)"

echo ""
echo "🔧 Probando importación de la aplicación..."
if python -c "from app.main import app; print('✅ Aplicación importada correctamente')" 2>&1; then
    echo "✅ Aplicación importada exitosamente"
else
    echo "⚠️ Advertencia: Error al importar la aplicación, pero continuando..."
    echo "Detalles del error:"
    python -c "from app.main import app" 2>&1 || true
fi

echo ""
echo "🌐 Iniciando servidor Gunicorn..."
echo "Puerto: ${PORT:-8000}"
echo "Bind: 0.0.0.0:${PORT:-8000}"
echo "Workers: 2"

# Usar uvicorn directamente para simplificar
echo ""
echo "🚀 Iniciando con Uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --log-level info \
    --no-access-log
