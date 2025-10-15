# Script para limpiar el puerto 5173 (Vite dev server)
Write-Host "Limpiando puerto 5173..." -ForegroundColor Yellow

# Buscar procesos que usen el puerto 5173
$processes = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess

if ($processes) {
    Write-Host "Encontrados procesos usando el puerto 5173:" -ForegroundColor Red
    foreach ($processId in $processes) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "PID: $processId - Nombre: $($process.ProcessName)" -ForegroundColor Red
        }
    }
    
    # Preguntar si terminar los procesos
    $response = Read-Host "¿Desea terminar estos procesos? (s/n)"
    if ($response -eq 's' -or $response -eq 'S') {
        foreach ($processId in $processes) {
            try {
                Stop-Process -Id $processId -Force
                Write-Host "Proceso $processId terminado" -ForegroundColor Green
            } catch {
                $errorMsg = $_.Exception.Message
                Write-Host "Error al terminar proceso $processId`: $errorMsg" -ForegroundColor Red
                
            }
        }
        Write-Host "Puerto 5173 liberado" -ForegroundColor Green
    } else {
        Write-Host "Operación cancelada" -ForegroundColor Yellow
    }
} else {
    Write-Host "No se encontraron procesos usando el puerto 5173" -ForegroundColor Green
}

Write-Host "Presione cualquier tecla para continuar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
