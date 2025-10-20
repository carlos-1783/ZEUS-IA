@echo off
title ZEUS-IA Deteniendo...

echo.
echo ========================================
echo      ZEUS-IA - Deteniendo Sistema
echo ========================================
echo.

echo Deteniendo Backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %%a 2>nul
echo OK

echo Deteniendo Frontend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %%a 2>nul
echo OK

echo.
echo ========================================
echo        ZEUS-IA DETENIDO
echo ========================================
echo.
pause

