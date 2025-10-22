#!/bin/bash

# ========================================
# ZEUS-IA - Configure Railway Variables
# ========================================

echo ""
echo "========================================"
echo "ZEUS-IA - Configurando Railway"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Railway CLI
echo -e "${YELLOW}[1] Verificando Railway CLI...${NC}"
if ! command -v railway &> /dev/null; then
    echo -e "${RED}ERROR: Railway CLI no está instalado${NC}"
    echo ""
    echo "Instálalo con: npm install -g @railway/cli"
    echo "O configura manualmente en: https://railway.app/dashboard"
    exit 1
fi

echo -e "${GREEN}[OK] Railway CLI encontrado${NC}"
echo ""

# Set variables
echo -e "${YELLOW}[2] Configurando variables de entorno...${NC}"
railway variables set SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b1cb7ddc2071ad633aee3c8568d62b13b
railway variables set REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c92189f25be3acd36ad07096d
railway variables set ACCESS_TOKEN_EXPIRE_MINUTES=30
railway variables set REFRESH_TOKEN_EXPIRE_DAYS=7
railway variables set JWT_ISSUER=zeus-ia-backend
railway variables set DEBUG=False
railway variables set ENVIRONMENT=production
railway variables set BACKEND_CORS_ORIGINS=https://zeus-ia-frontend-production.vercel.app,https://zeus-ia-production-16d8.up.railway.app

echo ""
echo -e "${YELLOW}[3] Reiniciando servicio...${NC}"
railway restart

echo ""
echo "========================================"
echo -e "${GREEN}Variables configuradas exitosamente!${NC}"
echo "========================================"
echo ""
echo "Espera 2-3 minutos para que Railway se redespliegue"
echo "Luego:"
echo "1. Abre el frontend"
echo "2. Haz logout/login"
echo "3. Verifica que WebSocket funciona"
echo ""

