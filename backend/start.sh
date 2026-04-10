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

if [ "${STARTUP_SELF_TEST:-false}" = "true" ]; then
  echo ""
  echo "🔧 Probando importación de la aplicación (STARTUP_SELF_TEST=true)..."
  if python -c "from app.main import app; print('✅ Aplicación importada correctamente')" 2>&1; then
      echo "✅ Aplicación importada exitosamente"
  else
      echo "⚠️ Advertencia: Error al importar la aplicación, pero continuando..."
      echo "Detalles del error:"
      python -c "from app.main import app" 2>&1 || true
  fi
fi

echo ""
echo "🚀 Iniciando con Uvicorn (single process en Railway)..."
echo "Puerto: ${PORT:-8000}"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --log-level info \
    --log-config uvicorn_log_config.json \
    --no-access-log
