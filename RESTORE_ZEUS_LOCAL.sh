#!/bin/bash

# ========================================
# ZEUS-IA - Restaurar Local Storage
# ========================================

echo ""
echo "========================================"
echo "ZEUS-IA - Restaurando Local Storage"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[1] Limpiando Local Storage...${NC}"

# Create JavaScript to clear storage
cat > temp_clear.js << 'EOF'
localStorage.clear();
sessionStorage.clear();
console.log("✅ Local Storage limpiado completamente");
alert("✅ Local Storage limpiado - Recarga la página");
EOF

echo -e "${GREEN}[OK] Script de limpieza creado${NC}"
echo ""

echo -e "${YELLOW}[2] Abriendo navegador para limpiar...${NC}"
# Open browser with clear script
if command -v google-chrome &> /dev/null; then
    google-chrome --new-window "data:text/html,<script>localStorage.clear();sessionStorage.clear();alert('✅ Local Storage limpiado - Recarga la página');</script>"
elif command -v firefox &> /dev/null; then
    firefox "data:text/html,<script>localStorage.clear();sessionStorage.clear();alert('✅ Local Storage limpiado - Recarga la página');</script>"
else
    echo "Abre tu navegador y ejecuta: localStorage.clear(); sessionStorage.clear();"
fi

echo ""
echo -e "${YELLOW}[3] Verificando URLs correctas...${NC}"
echo ""
echo "Backend (API): https://zeus-ia-production-16d8.up.railway.app/health"
echo "Frontend: https://zeus-ia-production-16d8.up.railway.app/"
echo ""

echo -e "${YELLOW}[4] Si el frontend no carga, usar Vercel:${NC}"
echo "cd frontend"
echo "vercel --prod"
echo ""

echo "========================================"
echo -e "${GREEN}Restauración completada${NC}"
echo "========================================"
echo ""

