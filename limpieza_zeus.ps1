
# Script de limpieza para ZEUS-IA (versión interactiva)
# Ejecuta este script en PowerShell desde la raíz del proyecto

Write-Host "[1/6] Archivos duplicados y de backup:"
$archivos = @(
    "cleanup_port_8001.bat", "cleanup.ps1", "free_port.bat", "free_port.ps1", "kill_port.ps1",
    "debug_backend.bat", "debug-backend.bat", "start_backend.bat", "start-backend.bat",
    "run.ps1.backup", "cleanup_duplicates.backup.ps1", "cleanup_log_20250709.txt",
    "websocket-test.html", "requirements.txt"
)
foreach ($f in $archivos) {
    if (Test-Path $f) {
        Write-Host "Eliminando $f"
        Remove-Item -Force $f
    }
}

Write-Host "[2/6] Archivos de prueba fuera de backend/tests:"
$testFiles = Get-ChildItem -Path . -Include "test-login.ps1", "test_*.py" -Recurse | Where-Object { $_.FullName -notmatch "backend\\tests" }
foreach ($t in $testFiles) {
    Write-Host "Eliminando $($t.FullName)"
    Remove-Item -Force $t.FullName
}

Write-Host "[3/6] Carpetas __pycache__:"
$pycacheDirs = Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__"
foreach ($d in $pycacheDirs) {
    Write-Host "Eliminando carpeta $($d.FullName)"
    Remove-Item -Recurse -Force $d.FullName
}

Write-Host "[4/6] Archivos .bak, .old, .backup:"
$bakFiles = Get-ChildItem -Path . -Include *.bak,*.old,*.backup -Recurse
foreach ($b in $bakFiles) {
    Write-Host "Eliminando $($b.FullName)"
    Remove-Item -Force $b.FullName
}

Write-Host "[5/6] Archivos .log:"
$logFiles = Get-ChildItem -Path . -Include *.log -Recurse
foreach ($l in $logFiles) {
    Write-Host "Eliminando $($l.FullName)"
    Remove-Item -Force $l.FullName
}

Write-Host "[6/6] Limpieza completada. Revisa antes de ejecutar en producción."
