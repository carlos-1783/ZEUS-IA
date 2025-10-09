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
echo "Bind: 0.0.0.0:${PORT:-8000}"
echo "Workers: $(python -c 'import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)')"

exec gunicorn app.main:app \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
