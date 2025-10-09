@echo off
echo Freeing port 8001...

:: Find and kill processes using port 8001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo Killing process with PID: %%a
    taskkill /F /PID %%a
)

echo.
echo If port 8001 is still in use, you may need to:
echo 1. Run this script as Administrator
echo 2. Restart your computer
echo 3. Check for services using the port

echo.
pause
