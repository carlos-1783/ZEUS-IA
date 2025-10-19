# Script para limpiar Service Worker y cache en desarrollo
Write-Host "🧹 Limpiando Service Worker y cache..." -ForegroundColor Yellow

# Limpiar cache del navegador (solo funciona si el navegador está abierto)
Write-Host "📝 Instrucciones para limpiar manualmente:" -ForegroundColor Cyan
Write-Host "1. Abre DevTools (F12)" -ForegroundColor White
Write-Host "2. Ve a Application > Storage" -ForegroundColor White
Write-Host "3. Haz clic en 'Clear storage'" -ForegroundColor White
Write-Host "4. O ve a Application > Service Workers" -ForegroundColor White
Write-Host "5. Haz clic en 'Unregister' en el service worker" -ForegroundColor White

# Limpiar archivos de cache de Vite
if (Test-Path "node_modules/.vite") {
    Remove-Item -Recurse -Force "node_modules/.vite"
    Write-Host "✅ Cache de Vite limpiado" -ForegroundColor Green
}

if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
    Write-Host "✅ Directorio dist limpiado" -ForegroundColor Green
}

if (Test-Path "dev-dist") {
    Remove-Item -Recurse -Force "dev-dist"
    Write-Host "✅ Directorio dev-dist limpiado" -ForegroundColor Green
}

Write-Host "🔄 Reinicia el servidor de desarrollo para aplicar cambios" -ForegroundColor Yellow
Write-Host "   npm run dev" -ForegroundColor White
