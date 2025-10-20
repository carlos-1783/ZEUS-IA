# ZEUS-IA - Script de Detención
Write-Host ""
Write-Host "========================================" -ForegroundColor Red
Write-Host "      ZEUS-IA - Deteniendo Sistema     " -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""

# Detener Backend (puerto 8000)
Write-Host "Deteniendo Backend..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "OK - Backend detenido" -ForegroundColor Green
}

# Detener Frontend (puerto 5173)
Write-Host "Deteniendo Frontend..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "OK - Frontend detenido" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "       ZEUS-IA DETENIDO OK             " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Presiona cualquier tecla para cerrar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

