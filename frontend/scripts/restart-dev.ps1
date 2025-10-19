# Script para limpiar Service Worker y reiniciar el servidor de desarrollo
Write-Host "🔄 Reiniciando servidor de desarrollo..." -ForegroundColor Cyan

# Detener cualquier proceso de Vite que esté ejecutándose
Write-Host "🛑 Deteniendo procesos de Vite..." -ForegroundColor Yellow
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq "node" } | Stop-Process -Force -ErrorAction SilentlyContinue

# Limpiar archivos de Service Worker
Write-Host "🧹 Limpiando archivos de Service Worker..." -ForegroundColor Yellow
if (Test-Path "dev-dist") {
    Get-ChildItem -Path "dev-dist" -Filter "workbox-*.js" | Remove-Item -Force
    Get-ChildItem -Path "dev-dist" -Filter "workbox-*.js.map" | Remove-Item -Force
    Get-ChildItem -Path "dev-dist" -Filter "sw.js" | Remove-Item -Force
    Get-ChildItem -Path "dev-dist" -Filter "sw.js.map" | Remove-Item -Force
    Get-ChildItem -Path "dev-dist" -Filter "suppress-warnings.js" | Remove-Item -Force
    Write-Host "✅ Archivos de Service Worker eliminados" -ForegroundColor Green
}

# Limpiar cache de Vite
Write-Host "🧹 Limpiando cache de Vite..." -ForegroundColor Yellow
if (Test-Path "node_modules/.vite") {
    Remove-Item -Path "node_modules/.vite" -Recurse -Force
    Write-Host "✅ Cache de Vite eliminado" -ForegroundColor Green
}

# Esperar un momento
Start-Sleep -Seconds 2

# Reiniciar el servidor de desarrollo
Write-Host "🚀 Iniciando servidor de desarrollo..." -ForegroundColor Green
npm run dev
