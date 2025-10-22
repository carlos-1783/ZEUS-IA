#!/bin/bash

# ========================================
# ZEUS-IA - Deploy Frontend AHORA
# ========================================

echo ""
echo "========================================"
echo "ZEUS-IA - Deploy Frontend URGENTE"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Vercel CLI
echo -e "${YELLOW}[1] Verificando Vercel CLI...${NC}"
if ! command -v vercel &> /dev/null; then
    echo -e "${RED}ERROR: Vercel CLI no está instalado${NC}"
    echo ""
    echo -e "${YELLOW}Instalando Vercel CLI...${NC}"
    npm install -g vercel
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: No se pudo instalar Vercel CLI${NC}"
        echo ""
        echo -e "${YELLOW}OPCIÓN MANUAL:${NC}"
        echo "1. Ir a: https://vercel.com/dashboard"
        echo "2. Click 'New Project'"
        echo "3. Conectar GitHub repo"
        echo "4. Seleccionar carpeta frontend"
        echo "5. Deploy"
        exit 1
    fi
fi

echo -e "${GREEN}[OK] Vercel CLI encontrado${NC}"
echo ""

# Go to frontend directory
echo -e "${YELLOW}[2] Yendo a carpeta frontend...${NC}"
cd frontend || {
    echo -e "${RED}ERROR: No se encontró la carpeta frontend${NC}"
    exit 1
}

# Install dependencies
echo -e "${YELLOW}[3] Instalando dependencias...${NC}"
npm install || {
    echo -e "${RED}ERROR: Falló la instalación de dependencias${NC}"
    exit 1
}

# Build
echo -e "${YELLOW}[4] Build para producción...${NC}"
npm run build || {
    echo -e "${RED}ERROR: Falló el build${NC}"
    exit 1
}

# Deploy
echo -e "${YELLOW}[5] Deploy en Vercel...${NC}"
vercel --prod || {
    echo -e "${RED}ERROR: Falló el deploy en Vercel${NC}"
    echo ""
    echo -e "${YELLOW}OPCIÓN MANUAL:${NC}"
    echo "1. Ir a: https://vercel.com/dashboard"
    echo "2. Click 'New Project'"
    echo "3. Conectar GitHub repo"
    echo "4. Seleccionar carpeta frontend"
    echo "5. Deploy"
    exit 1
}

echo ""
echo "========================================"
echo -e "${GREEN}Frontend desplegado exitosamente!${NC}"
echo "========================================"
echo ""
echo -e "${YELLOW}IMPORTANTE: Configurar variables en Vercel:${NC}"
echo "VITE_API_URL=https://zeus-ia-production-16d8.up.railway.app/api/v1"
echo "VITE_WS_URL=wss://zeus-ia-production-16d8.up.railway.app/api/v1/ws"
echo ""

