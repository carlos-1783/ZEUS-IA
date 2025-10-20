# REINICIAR COMPLETO ZEUS-IA
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    REINICIANDO ZEUS-IA COMPLETAMENTE" -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan

# 1. MATAR TODOS LOS PROCESOS
Write-Host "[1/6] Matando todos los procesos..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" -or $_.ProcessName -like "*uvicorn*" -or $_.ProcessName -like "*vite*"} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2. LIBERAR PUERTOS
Write-Host "[2/6] Liberando puertos..." -ForegroundColor Yellow
netstat -ano | findstr ":8000" | ForEach-Object { $processId = ($_ -split '\s+')[-1]; if ($processId) { taskkill /F /PID $processId 2>$null } }
netstat -ano | findstr ":5173" | ForEach-Object { $processId = ($_ -split '\s+')[-1]; if ($processId) { taskkill /F /PID $processId 2>$null } }
Start-Sleep -Seconds 2

# 3. LIMPIAR CACHÉ DE NODE
Write-Host "[3/6] Limpiando caché de Node..." -ForegroundColor Yellow
if (Test-Path "frontend/node_modules/.vite") { Remove-Item -Recurse -Force "frontend/node_modules/.vite" -ErrorAction SilentlyContinue }
if (Test-Path "frontend/dist") { Remove-Item -Recurse -Force "frontend/dist" -ErrorAction SilentlyContinue }

# 4. REINSTALAR DEPENDENCIAS
Write-Host "[4/6] Reinstalando dependencias..." -ForegroundColor Yellow
Set-Location "frontend"
npm install --force
Set-Location ".."

# 5. INICIAR BACKEND
Write-Host "[5/6] Iniciando Backend..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000", "--host", "0.0.0.0" -WindowStyle Hidden -WorkingDirectory "backend"

# Esperar que el backend inicie
Start-Sleep -Seconds 5

# 6. INICIAR FRONTEND
Write-Host "[6/6] Iniciando Frontend..." -ForegroundColor Yellow
Set-Location "frontend"
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Hidden
Set-Location ".."

Write-Host "========================================" -ForegroundColor Green
Write-Host "    ZEUS-IA REINICIADO COMPLETAMENTE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANTE: Abre el navegador en modo incógnito" -ForegroundColor Red
Write-Host "O ejecuta en la consola del navegador:" -ForegroundColor Red
Write-Host "localStorage.clear(); sessionStorage.clear(); location.reload()" -ForegroundColor Red
Write-Host ""
Write-Host "Credenciales:" -ForegroundColor Cyan
Write-Host "  Email:    marketingdigitalper.seo@gmail.com" -ForegroundColor White
Write-Host "  Password: Carnay19" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green

# Abrir navegador en modo incógnito
Start-Sleep -Seconds 3
Start-Process "chrome.exe" -ArgumentList "--incognito", "http://localhost:5173/auth/login"
