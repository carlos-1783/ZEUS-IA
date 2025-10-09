@echo off
echo Finding and killing processes using port 8000...

:: Find PIDs using port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing process with PID: %%a
    taskkill /F /PID %%a
)

echo Cleanup complete.
pause
