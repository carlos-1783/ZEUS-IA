# Force cleanup of port 8000
Write-Host "=== FORCE CLEANUP PORT 8000 ==="

# Function to stop process by port
function Stop-ProcessOnPort {
    param([int]$port)
    
    Write-Host "Looking for processes using port $port..."
    
    # Method 1: Using Get-NetTCPConnection
    $processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | 
                Where-Object { $_.State -eq 'Listen' } | 
                Select-Object -ExpandProperty OwningProcess -Unique |
                ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }
    
    # Method 2: Using netstat (as fallback)
    if (-not $processes) {
        $netstatOutput = netstat -ano | findstr ":$port" | findstr "LISTENING"
        if ($netstatOutput) {
            $pidMatch = [regex]::Match($netstatOutput, '\s+(\d+)$')
            if ($pidMatch.Success) {
                $processes = Get-Process -Id $pidMatch.Groups[1].Value -ErrorAction SilentlyContinue
            }
        }
    }
    
    # Kill found processes
    if ($processes) {
        $processes | ForEach-Object {
            $procName = $_.ProcessName
            $procId = $_.Id
            Write-Host "Found process $procName (PID: $procId) using port $port"
            
            try {
                Write-Host "Attempting to stop process $procName (PID: $procId)..."
                $_.Kill()
                Start-Sleep -Seconds 1
                
                # Verify process is gone
                if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
                    Write-Host "Failed to stop process $procName (PID: $procId)"
                    return $false
                }
                Write-Host "Successfully stopped process $procName (PID: $procId)"
            } catch {
                Write-Host "Error stopping process $procName (PID: $procId): $_"
                return $false
            }
        }
        return $true
    } else {
        Write-Host "No processes found using port $port"
        return $true
    }
}

# Main execution
$port = 8000

# Stop processes on the port
Stop-ProcessOnPort -port $port

# Verify port is free
$portInUse = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -ErrorAction SilentlyContinue

if ($portInUse) {
    Write-Host "Port $port is still in use after cleanup. Additional steps required:"
    Write-Host "1. Check for Windows services using the port"
    Write-Host "2. Check for system processes that might be holding the port"
    Write-Host "3. Consider restarting the system if the port remains in use"
    exit 1
} else {
    Write-Host "Port $port is now available."
    exit 0
}
