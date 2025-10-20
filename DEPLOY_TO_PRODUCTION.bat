@echo off
echo ========================================
echo    DEPLOYING ZEUS-IA TO PRODUCTION
echo ========================================

echo [1/3] Adding all files to git...
git add . --quiet

echo [2/3] Committing changes...
git commit -m "Ready for production deployment" --quiet

echo [3/3] Pushing to GitHub...
git push origin main --quiet

echo ========================================
echo    DEPLOYMENT INITIATED SUCCESSFULLY
echo ========================================
echo.
echo Next steps:
echo 1. Go to Railway dashboard
echo 2. Connect your GitHub repository
echo 3. Deploy automatically
echo.
echo Your ZEUS-IA is ready for production!
echo ========================================

pause
