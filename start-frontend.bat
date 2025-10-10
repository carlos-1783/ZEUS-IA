@echo off
setlocal enabledelayedexpansion

title ZEUS-IA Frontend
echo [%TIME%] Starting ZEUS-IA Frontend...
cd /d "C:\Users\Acer\ZEUS-IA\frontend"

echo Installing dependencies...
call npm install --no-audit --no-fund
if !ERRORLEVEL! NEQ 0 (
  echo [ERROR] Failed to install frontend dependencies
  pause
  exit /b 1
)

echo Starting development server...
call npm run dev

if !ERRORLEVEL! NEQ 0 (
  echo [ERROR] Failed to start development server
  pause
  exit /b 1
)

pause
