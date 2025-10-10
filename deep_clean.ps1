# Stop all Python and Uvicorn processes
Stop-Process -Name "python*" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "uvicorn*" -Force -ErrorAction SilentlyContinue

# Kill processes using port 8001
try {
    $process = Get-NetTCPConnection -LocalPort 8001 -ErrorAction Stop | 
              Select-Object -ExpandProperty OwningProcess -ErrorAction Stop | 
              Get-Process -ErrorAction Stop
    
    if ($process) {
        Write-Host "Killing processes using port 8001:"
        $process | ForEach-Object {
            Write-Host "- $($_.ProcessName) (PID: $($_.Id))"
            Stop-Process -Id $_.Id -Force
        }
    } else {
        Write-Host "No processes found using port 8001."
    }
} catch {
    Write-Host "Error checking processes on port 8001: $_"
}

# Additional cleanup for common Python processes
$processes = @("python", "python3", "pythonw", "uvicorn")
foreach ($proc in $processes) {
    try {
        $running = Get-Process -Name $proc -ErrorAction Stop
        if ($running) {
            Write-Host "Stopping $proc processes..."
            Stop-Process -Name $proc -Force -ErrorAction Stop
        }
    } catch {
        # Process not found, continue
    }
}

Write-Host "Cleanup complete. Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
