#!/bin/bash

echo "========================================"
echo "REBUILD FRONTEND PARA RAILWAY"
echo "========================================"
echo ""

cd frontend

echo "[1/4] Limpiando cache y node_modules..."
rm -rf node_modules dist node_modules/.vite

echo ""
echo "[2/4] Instalando dependencias..."
npm ci

echo ""
echo "[3/4] Verificando vite.config.ts..."
if grep -q "base = '/'" vite.config.ts; then
    echo "✅ base: '/' configurado correctamente"
else
    echo "❌ ERROR: base no está configurado correctamente"
    exit 1
fi

echo ""
echo "[4/4] Construyendo frontend con configuración de producción..."
NODE_ENV=production npm run build

echo ""
echo "[5/6] Copiando build al backend..."
cd ..
rm -rf backend/static
cp -r frontend/dist backend/static

echo ""
echo "========================================"
echo "✅ BUILD COMPLETADO"
echo "========================================"
echo ""
echo "Archivos generados en:"
echo "- frontend/dist"
echo "- backend/static"
echo ""
echo "SIGUIENTE PASO:"
echo "1. Verifica que backend/static/index.html tenga rutas como /assets/js/..."
echo "2. Commitea los cambios"
echo "3. Push a Railway"
echo ""

