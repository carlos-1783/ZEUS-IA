# ZEUS-IA - Instalador de Dependencias
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ZEUS-IA - Instalando Dependencias    " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Instalar psutil en backend
Write-Host "[1/2] Instalando psutil (backend)..." -ForegroundColor Yellow
Set-Location backend
pip install psutil==5.9.8 --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - psutil instalado" -ForegroundColor Green
} else {
    Write-Host "ERROR - No se pudo instalar psutil" -ForegroundColor Red
}
Set-Location ..

# Instalar serve en frontend (si no existe)
Write-Host "[2/2] Verificando dependencias frontend..." -ForegroundColor Yellow
Set-Location frontend
if (!(Test-Path "node_modules")) {
    Write-Host "Instalando dependencias de frontend (puede tardar)..." -ForegroundColor Yellow
    npm install --loglevel=error
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK - Dependencias instaladas" -ForegroundColor Green
    }
} else {
    Write-Host "OK - Dependencias ya instaladas" -ForegroundColor Green
}
Set-Location ..

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "      DEPENDENCIAS INSTALADAS OK       " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Ahora ejecuta: START-ZEUS.ps1" -ForegroundColor Cyan
Write-Host ""

Write-Host "Presiona cualquier tecla para cerrar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

