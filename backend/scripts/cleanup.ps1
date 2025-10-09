# Script to forcefully clean up port 8000
Write-Host "=== ZEUS-IA Port Cleanup Utility ==="
Write-Host "Checking for processes using port 8000..."

# Find processes using port 8000
$processes = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
             Where-Object { $_.State -eq 'Listen' } | 
             Select-Object -ExpandProperty OwningProcess -Unique |
             ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }

if ($processes) {
    Write-Host "Found the following processes using port 8000:"
    $processes | Format-Table Id, ProcessName, Path -AutoSize
    
    # Kill the processes
    $processes | ForEach-Object {
        $procName = $_.ProcessName
        $procId = $_.Id
        Write-Host "Stopping process $procName (PID: $procId)..."
        try {
            # Try graceful shutdown first
            $_.CloseMainWindow() | Out-Null
            if (!$_.WaitForExit(2000)) {
                Write-Host "Forcefully terminating process $procName (PID: $procId)..."
                $_.Kill()
            }
            Write-Host "Process $procName (PID: $procId) stopped."
        } catch {
            Write-Host "Error stopping process $procName (PID: $procId): $_"
        }
    }
} else {
    Write-Host "No processes found using port 8000."
}

# Double check with netstat
Write-Host "`nVerifying port status..."
$portInUse = Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet -ErrorAction SilentlyContinue

if ($portInUse) {
    Write-Host "Port 8000 is still in use. Trying alternative method..."
    
    # Use netstat to find the process
    $netstatOutput = netstat -ano | findstr ":8000" | findstr "LISTENING"
    if ($netstatOutput) {
        $pidMatch = [regex]::Match($netstatOutput, '\s+(\d+)$')
        if ($pidMatch.Success) {
            $pidToKill = $pidMatch.Groups[1].Value
            Write-Host "Found process with PID $pidToKill using port 8000"
            
            # Try to get process info
            $process = Get-Process -Id $pidToKill -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Process details: $($process.ProcessName) (PID: $($process.Id))"
                Write-Host "Attempting to stop the process..."
                try {
                    $process | Stop-Process -Force -ErrorAction Stop
                    Write-Host "Process stopped successfully."
                } catch {
                    Write-Host "Failed to stop process: $_"
                }
            } else {
                Write-Host "Process not found. It might have already been terminated."
            }
        }
    }
} else {
    Write-Host "Port 8000 is now available."
}

Write-Host "`nCleanup complete. You can now try starting the application again."
