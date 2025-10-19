# Script simple para matar procesos en el puerto 5173
Write-Host "Buscando procesos en el puerto 5173..." -ForegroundColor Yellow

try {
    $connections = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $processId = $conn.OwningProcess
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Terminando proceso: $($process.ProcessName) (PID: $processId)" -ForegroundColor Red
                Stop-Process -Id $processId -Force
            }
        }
        Write-Host "Puerto 5173 liberado" -ForegroundColor Green
    } else {
        Write-Host "No se encontraron procesos en el puerto 5173" -ForegroundColor Green
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
