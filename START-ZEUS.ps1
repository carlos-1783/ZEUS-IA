# ZEUS-IA - Script de Inicio
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "      ZEUS-IA - Iniciando Sistema      " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Liberar puerto 8000
Write-Host "[1/4] Liberando puerto 8000..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Write-Host "OK" -ForegroundColor Green

# Liberar puerto 5173
Write-Host "[2/4] Liberando puerto 5173..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Write-Host "OK" -ForegroundColor Green

# Iniciar Backend
Write-Host "[3/4] Iniciando Backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn app.main:app --reload --port 8000" -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "OK - Backend en http://localhost:8000" -ForegroundColor Green

# Iniciar Frontend
Write-Host "[4/4] Iniciando Frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev" -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "OK - Frontend en http://localhost:5173" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "        ZEUS-IA INICIADO OK            " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Accede en: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "Credenciales:" -ForegroundColor Yellow
Write-Host "  Email:    marketingdigitalper.seo@gmail.com"
Write-Host "  Password: Carnay19"
Write-Host ""
Write-Host "Para detener: ejecuta STOP-ZEUS.ps1" -ForegroundColor Red
Write-Host ""

# Abrir navegador
Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"

Write-Host "Presiona cualquier tecla para cerrar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

