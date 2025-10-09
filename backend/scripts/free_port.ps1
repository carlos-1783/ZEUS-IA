# Script to free a specific port
param(
    [Parameter(Mandatory=$true)]
    [int]$Port
)

Write-Host "Freeing port $Port..." -ForegroundColor Yellow

# Find and kill processes using the port
$processes = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
             Where-Object { $_.State -eq 'Listen' } | 
             Select-Object -ExpandProperty OwningProcess -Unique

if ($processes) {
    foreach ($processId in $processes) {
        try {
            $process = Get-Process -Id $processId -ErrorAction Stop
            Write-Host "Killing process: $($process.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction Stop
        } catch {
            Write-Host ("Error killing process {0}: {1}" -f $processId, $_.Exception.Message) -ForegroundColor Red
        }
    }
} else {
    Write-Host "No processes found using port $Port" -ForegroundColor Green
}

# Verify the port is free
$portInUse = Test-NetConnection -ComputerName localhost -Port $Port -ErrorAction SilentlyContinue | 
             Where-Object { $_.TcpTestSucceeded -eq $true }

if ($portInUse) {
    Write-Host "Port $Port is still in use. Trying alternative method..." -ForegroundColor Red
    
    # Try using netstat to find the process
    $netstatOutput = netstat -ano | findstr ":$Port" | findstr "LISTENING"
    if ($netstatOutput) {
        Write-Host "Found processes using netstat:" -ForegroundColor Yellow
        $netstatOutput
        
        # Extract and kill PIDs
        $netstatOutput | ForEach-Object {
            $pidToKill = $_ -replace '\s+', ' ' -split ' ' | Select-Object -Last 1
            if ($pidToKill -match '\d+') {
                Write-Host "Killing process with PID: $pidToKill" -ForegroundColor Yellow
                try {
                    Stop-Process -Id $pidToKill -Force -ErrorAction Stop
                    Write-Host "Successfully killed process $pidToKill" -ForegroundColor Green
                } catch {
                    Write-Host ("Failed to kill process {0}: {1}" -f $pidToKill, $_.Exception.Message) -ForegroundColor Red
                }
            }
        }
    }
} else {
    Write-Host "Port $Port is now free" -ForegroundColor Green
}

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
