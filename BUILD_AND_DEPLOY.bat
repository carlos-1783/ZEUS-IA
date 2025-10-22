@echo off
REM ========================================
REM ZEUS-IA - Build & Deploy Script (Windows)
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Build and Deploy
echo ========================================
echo.

REM 1. Frontend Build
echo [1/4] Building Frontend...
cd frontend
call npm install
call npm run build

IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)

echo [OK] Frontend build completed successfully
echo.

REM 2. Copy to Backend Static
echo [2/4] Copying frontend to backend/static...
cd ..
IF EXIST backend\static (
    rmdir /s /q backend\static
)
xcopy /E /I /Y frontend\dist backend\static

IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to copy frontend to backend!
    pause
    exit /b 1
)

echo [OK] Frontend copied to backend/static
echo.

REM 3. Test Backend Locally (Optional)
echo [3/4] Testing backend locally (optional)...
echo Press Ctrl+C to skip local testing
cd backend
REM Descomentar la siguiente línea para test local
REM python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.

REM 4. Commit and Push
echo [4/4] Committing changes...
cd ..
git add .
git commit -m "Build: Frontend compiled and ready for deployment"

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Push to Git: git push origin main
echo 2. Railway will auto-deploy the backend
echo 3. For frontend:
echo    - Vercel: vercel --prod
echo    - Netlify: netlify deploy --prod
echo.
echo Don't forget to configure environment variables!
echo See DEPLOYMENT_INSTRUCTIONS.md for details.
echo.

pause

