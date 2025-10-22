#!/bin/bash

# ========================================
# ZEUS-IA - Build & Deploy Script (Linux/Mac)
# ========================================

echo ""
echo "========================================"
echo "ZEUS-IA - Build and Deploy"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Frontend Build
echo -e "${YELLOW}[1/4] Building Frontend...${NC}"
cd frontend || exit 1
npm install
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Frontend build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Frontend build completed successfully${NC}"
echo ""

# 2. Copy to Backend Static
echo -e "${YELLOW}[2/4] Copying frontend to backend/static...${NC}"
cd ..
rm -rf backend/static
cp -r frontend/dist backend/static

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to copy frontend to backend!${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Frontend copied to backend/static${NC}"
echo ""

# 3. Test Backend Locally (Optional)
echo -e "${YELLOW}[3/4] Testing backend locally (optional)...${NC}"
echo "Press Ctrl+C to skip local testing"
cd backend || exit 1
# Uncomment the following line to test locally
# python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo ""

# 4. Commit and Push
echo -e "${YELLOW}[4/4] Committing changes...${NC}"
cd ..
git add .
git commit -m "Build: Frontend compiled and ready for deployment"

echo ""
echo "========================================"
echo -e "${GREEN}Build completed successfully!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Push to Git: git push origin main"
echo "2. Railway will auto-deploy the backend"
echo "3. For frontend:"
echo "   - Vercel: vercel --prod"
echo "   - Netlify: netlify deploy --prod"
echo ""
echo "Don't forget to configure environment variables!"
echo "See DEPLOYMENT_INSTRUCTIONS.md for details."
echo ""

