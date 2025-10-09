# PowerShell script to forcefully kill processes using a specific port
param(
    [Parameter(Mandatory=$true)]
    [int]$Port
)

Write-Host "Buscando procesos usando el puerto $Port..." -ForegroundColor Yellow

# Find the process using the port
$process = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
           Where-Object { $_.State -eq 'Listen' } | 
           Select-Object -ExpandProperty OwningProcess

if ($process) {
    Write-Host "Proceso encontrado con PID: $process" -ForegroundColor Yellow
    
    # Try graceful termination first
    try {
        Stop-Process -Id $process -Force -ErrorAction Stop
        Write-Host "Proceso terminado correctamente." -ForegroundColor Green
    } catch {
        Write-Host "No se pudo terminar el proceso normalmente. Intentando con taskkill..." -ForegroundColor Red
        
        # Use taskkill as a fallback
        $output = cmd /c "taskkill /F /PID $process 2>&1"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Proceso terminado con taskkill." -ForegroundColor Green
        } else {
            Write-Host "Error al terminar el proceso: $output" -ForegroundColor Red
        }
    }
} else {
    Write-Host "No se encontraron procesos usando el puerto $Port" -ForegroundColor Yellow
}

# Double check
$stillRunning = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($stillRunning) {
    Write-Host "\nADVERTENCIA: El puerto $Port todav¡a est  en uso:" -ForegroundColor Red
    $stillRunning | Format-Table -AutoSize
    
    # Try to find the process using netstat
    Write-Host "\nBuscando con netstat..." -ForegroundColor Yellow
    $netstatOutput = netstat -ano | findstr ":$Port" | findstr "LISTENING"
    if ($netstatOutput) {
        Write-Host "Netstat encontr¢ los siguientes procesos:" -ForegroundColor Yellow
        $netstatOutput
        
        # Extract PID from netstat output
        $pidMatch = [regex]::Match($netstatOutput, '\s+(\d+)$')
        if ($pidMatch.Success) {
            $pidToKill = $pidMatch.Groups[1].Value
            Write-Host "\nIntentando terminar el proceso con PID: $pidToKill" -ForegroundColor Yellow
            
            try {
                Stop-Process -Id $pidToKill -Force -ErrorAction Stop
                Write-Host "Proceso $pidToKill terminado correctamente." -ForegroundColor Green
            } catch {
                Write-Host "No se pudo terminar el proceso $pidToKill: $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "No se encontraron procesos adicionales con netstat." -ForegroundColor Yellow
    }
} else {
    Write-Host "\nEl puerto $Port est  libre para su uso." -ForegroundColor Green
}

Write-Host "\nPresione cualquier tecla para continuar..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
