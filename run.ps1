# run.ps1 - Optimized Startup Script for ZEUS IA
# Version: 4.1
# Description: Enhanced startup script with reliable backend and frontend process management

# Set Error Action Preference and encoding
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Enable TLS 1.2 for secure connections
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Constants
# Backend server port
$BACKEND_PORT = 8000
$FRONTEND_PORT = 5173
$BACKEND_URL = "http://localhost:$BACKEND_PORT"
$SCRIPT_DIR = $PSScriptRoot
$LOG_FILE = Join-Path -Path $SCRIPT_DIR -ChildPath "logs/zeus_startup_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
$MAX_RETRIES = 3
$RETRY_DELAY = 2
$MAX_RETRY_DELAY = 30

# Create logs directory if it doesn't exist
$logDir = Join-Path -Path $SCRIPT_DIR -ChildPath "logs"
if (-not (Test-Path -Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,
        
        [ValidateSet('INFO', 'WARN', 'ERROR', 'SUCCESS', 'DEBUG')]
        [string]$Level = 'INFO',
        
        [switch]$NoConsoleOutput
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $logMessage = "[$timestamp] [$Level] $Message"
    
    # Add to log file
    $logMessage | Out-File -FilePath $LOG_FILE -Append -Encoding UTF8 -Force
    
    # Output to console unless suppressed
    if (-not $NoConsoleOutput) {
        $foregroundColor = switch ($Level) {
            'SUCCESS' { 'Green' }
            'WARN'    { 'Yellow' }
            'ERROR'   { 'Red' }
            'DEBUG'   { 'Gray' }
            default   { 'White' }
        }
        
        Write-Host "[$($Level.PadRight(7))] $Message" -ForegroundColor $foregroundColor
    }
}

function Test-PortInUse {
    [CmdletBinding()]
    param([int]$Port)
    
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $result = $tcpClient.ConnectAsync("localhost", $Port).Wait(1000)
        $tcpClient.Close()
        return $result
    } catch {
        return $false
    }
}

function Stop-ProcessIfRunning {
    [CmdletBinding()]
    param(
        [Parameter(ParameterSetName='ByName')]
        [string]$ProcessName,
        
        [Parameter(ParameterSetName='ByPort')]
        [int]$Port,
        
        [switch]$Force
    )
    
    $processes = @()
    
    if ($ProcessName) {
        $processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | 
                    Where-Object { $_.MainWindowTitle -notlike "*powershell*" -and $_.ProcessName -ne 'powershell' }
    }
    
    if ($Port -gt 0) {
        $processes += Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
                     Select-Object -ExpandProperty OwningProcess -Unique | 
                     ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }
    }
    
    foreach ($process in $processes) {
        try {
            if (-not $process.HasExited) {
                Write-Log "Stopping process: $($process.ProcessName) (PID: $($process.Id))" -Level INFO
                
                if ($process.CloseMainWindow() -and $process.WaitForExit(2000)) {
                    Write-Log "Process stopped gracefully" -Level SUCCESS
                    continue
                }
                
                if ($Force -or -not $process.HasExited) {
                    $process.Kill()
                    if ($process.WaitForExit(1000)) {
                        Write-Log "Process force stopped" -Level WARN
                    }
                }
            }
        } catch {
            Write-Log "Error stopping process: $_" -Level ERROR
        }
    }
}

function Start-BackendServer {
    [CmdletBinding()]
    param(
        [int]$Port = $BACKEND_PORT,
        [int]$RetryCount = 0
    )
    
    $maxRetries = $MAX_RETRIES
    $retryDelay = $RETRY_DELAY
    
    if (Test-PortInUse -Port $Port) {
        Write-Log "Port $Port is in use. Attempting to free it..." -Level WARN
        Stop-ProcessIfRunning -Port $Port -Force
        
        if (Test-PortInUse -Port $Port) {
            throw "Failed to free port $Port"
        }
    }
    
    $backendDir = Join-Path -Path $SCRIPT_DIR -ChildPath "app"
    $pythonCmd = "python"
    $hostAddr = "0.0.0.0"
    
    Write-Log "Starting backend server..." -Level INFO
    
    $retry = 0
    $operationSuccess = $false
    
    while ($retry -le $maxRetries -and -not $operationSuccess) {
        try {
            $processInfo = New-Object System.Diagnostics.ProcessStartInfo
            $processInfo.FileName = $pythonCmd
            $processInfo.Arguments = $uvicornCmd
            $processInfo.WorkingDirectory = $backendDir
            $processInfo.UseShellExecute = $false
            $processInfo.RedirectStandardOutput = $true
            $processInfo.RedirectStandardError = $true
            $processInfo.CreateNoWindow = $true
            
            $process = New-Object System.Diagnostics.Process
            $process.StartInfo = $processInfo
            
            # Configure process
            $process.StartInfo.RedirectStandardOutput = $true
            $process.StartInfo.RedirectStandardError = $true
            $process.StartInfo.UseShellExecute = $false
            $process.StartInfo.CreateNoWindow = $true
            
            # Run Python directly in the console to see the output
            Write-Log "Starting backend process directly..." -Level INFO
            
            # Create a temporary script to run the backend with proper argument handling
            $tempScript = Join-Path $env:TEMP "run_backend.ps1"
            
            @"
            # Set PYTHONPATH to include the project root directory
            `$env:PYTHONPATH = "$SCRIPT_DIR"
            
            # Change to the backend directory
            Set-Location "$backendDir"
            
            # Build and execute the command
            `$command = "$pythonCmd -m uvicorn app.main:app --host $hostAddr --port $Port --reload"
            Write-Host "Starting backend with: `$command"
            Write-Host "PYTHONPATH: `$env:PYTHONPATH"
            
            try {
                # Execute the command directly
                Invoke-Expression `$command
                
                if (`$LASTEXITCODE -ne 0) {
                    Write-Host "Backend failed to start with exit code: `$LASTEXITCODE" -ForegroundColor Red
                    exit `$LASTEXITCODE
                }
            } catch {
                Write-Host "Error starting backend: `$_" -ForegroundColor Red
                exit 1
            }
"@ | Out-File -FilePath $tempScript -Force -Encoding UTF8
            
            # Start the process in a new window
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { & `"$tempScript`" }" -WorkingDirectory $backendDir
            
            # Wait a moment for the process to start
            Start-Sleep -Seconds 2
            
            # Check if the process is still running
            if ($process.HasExited) {
                throw "Backend process failed to start. Check the console for errors."
            }
            
            # Wait for the backend to be ready
            $startTime = Get-Date
            $maxWaitTime = 30  # seconds
            $isReady = $false
            
            Write-Log "Waiting for backend to be ready..." -Level INFO
            
            while (((Get-Date) - $startTime).TotalSeconds -lt $maxWaitTime) {
                if ($process.HasExited) {
                    throw "Backend process exited with code $($process.ExitCode). Check the console for errors."
                }
                
                # Try to connect to the health check endpoint
                try {
                    $response = Invoke-WebRequest -Uri "http://localhost:$Port/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                    if ($response.StatusCode -eq 200) {
                        $isReady = $true
                        break
                    }
                } catch {
                    # Ignore connection errors, we'll retry
                }
                
                # Show status every 5 seconds
                if (((Get-Date).Second % 5) -eq 0) {
                    $elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)
                    Write-Log "Waiting for backend to start... (${elapsed}s elapsed)" -Level INFO
                }
                
                Start-Sleep -Seconds 1
            }
            
            if (-not $isReady) {
                $errorOutput = $errorTask.Result
                if (-not [string]::IsNullOrEmpty($errorOutput)) {
                    Write-Log "Backend error: $errorOutput" -Level ERROR
                }
                throw "Backend did not become ready within $maxWaitTime seconds"
            }
            
            $healthCheckUrl = "http://localhost:$Port/api/health"
            $maxWaitTime = 30
            $startTime = Get-Date
            $isReady = $false
            
            Write-Log "Waiting for backend to be ready..." -Level INFO
            
            while (((Get-Date) - $startTime).TotalSeconds -lt $maxWaitTime) {
                try {
                    $response = Invoke-WebRequest -Uri $healthCheckUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
                    if ($response.StatusCode -eq 200) {
                        $isReady = $true
                        Write-Log "Backend is ready and healthy" -Level SUCCESS
                        break
                    }
                } catch {
                    Start-Sleep -Milliseconds 500
                }
                
                if ($process.HasExited) {
                    throw "Backend process exited with code $($process.ExitCode)"
                }
                
                Start-Sleep -Milliseconds 500
            }
            
            if (-not $isReady) {
                throw "Backend did not become ready within $maxWaitTime seconds"
            }
            
            $operationSuccess = $true
            Write-Log "Backend server started successfully" -Level SUCCESS
            Write-Log "Backend URL: http://localhost:$Port" -Level INFO
            
            return $process
            
        } catch {
            $lastError = $_.Exception.Message
            $retry++
            
            if ($process -and -not $process.HasExited) {
                try { $process.Kill() } catch {}
            }
            
            if ($retry -le $maxRetries) {
                $delay = [Math]::Min($retryDelay * $retry, $MAX_RETRY_DELAY)
                Write-Log "Attempt $retry of $maxRetries failed: $lastError" -Level WARN
                Write-Log "Retrying in ${delay} seconds..." -Level WARN
                Start-Sleep -Seconds $delay
            } else {
                throw "Failed to start backend server after $maxRetries attempts. Last error: $lastError"
            }
        }
    }
}

function Start-FrontendServer {
    [CmdletBinding()]
    param(
        [int]$Port = $FRONTEND_PORT,
        [string]$BackendUrl = $BACKEND_URL,
        [int]$RetryCount = 0
    )
    
    $maxRetries = $MAX_RETRIES
    $retryDelay = $RETRY_DELAY
    
    if (Test-PortInUse -Port $Port) {
        Write-Log "Port $Port is in use. Attempting to free it..." -Level WARN
        Stop-ProcessIfRunning -Port $Port -Force
        
        if (Test-PortInUse -Port $Port) {
            throw "Failed to free port $Port"
        }
    }
    
    $frontendDir = Join-Path -Path $SCRIPT_DIR -ChildPath "frontend"
    $npmCmd = "npm"
    $startCmd = "run dev -- --port $Port --host"
    
    Write-Log "Starting frontend server..." -Level INFO
    
    $retry = 0
    $operationSuccess = $false
    
    while ($retry -le $maxRetries -and -not $operationSuccess) {
        try {
            $processInfo = New-Object System.Diagnostics.ProcessStartInfo
            $processInfo.FileName = $npmCmd
            $processInfo.Arguments = $startCmd
            $processInfo.WorkingDirectory = $frontendDir
            $processInfo.UseShellExecute = $false
            $processInfo.RedirectStandardOutput = $true
            $processInfo.RedirectStandardError = $true
            $processInfo.CreateNoWindow = $true
            
            $process = New-Object System.Diagnostics.Process
            $process.StartInfo = $processInfo
            
            # Directly use the script block for output handling
            $process.OutputDataReceived.Add_DataReceived({
                if (-not [string]::IsNullOrEmpty($_.Data)) {
                    Write-Log "[FRONTEND] $($_.Data)" -Level DEBUG -NoConsoleOutput
                }
            })
            
            $processStarted = $process.Start()
            if (-not $processStarted) {
                throw "Failed to start frontend process"
            }
            
            $process.BeginOutputReadLine()
            $process.BeginErrorReadLine()
            
            $maxWaitTime = 60
            $startTime = Get-Date
            $isReady = $false
            
            Write-Log "Waiting for frontend to be ready..." -Level INFO
            
            while (((Get-Date) - $startTime).TotalSeconds -lt $maxWaitTime) {
                try {
                    $response = Invoke-WebRequest -Uri "http://localhost:$Port" -Method Head -TimeoutSec 2 -ErrorAction Stop
                    if ($response.StatusCode -eq 200) {
                        $isReady = $true
                        Write-Log "Frontend is ready" -Level SUCCESS
                        break
                    }
                } catch {
                    Start-Sleep -Milliseconds 500
                }
                
                if ($process.HasExited) {
                    throw "Frontend process exited with code $($process.ExitCode)"
                }
                
                Start-Sleep -Milliseconds 500
            }
            
            if (-not $isReady) {
                throw "Frontend did not become ready within $maxWaitTime seconds"
            }
            
            $operationSuccess = $true
            Write-Log "Frontend server started successfully" -Level SUCCESS
            Write-Log "Frontend URL: http://localhost:$Port" -Level INFO
            
            return $process
            
        } catch {
            $lastError = $_.Exception.Message
            $retry++
            
            if ($process -and -not $process.HasExited) {
                try { $process.Kill() } catch {}
            }
            
            if ($retry -le $maxRetries) {
                $delay = [Math]::Min($retryDelay * $retry, $MAX_RETRY_DELAY)
                Write-Log "Attempt $retry of $maxRetries failed: $lastError" -Level WARN
                Write-Log "Retrying in ${delay} seconds..." -Level WARN
                Start-Sleep -Seconds $delay
            } else {
                throw "Failed to start frontend server after $maxRetries attempts. Last error: $lastError"
            }
        }
    }
}

function Start-ZeusApplication {
    [CmdletBinding()]
    param(
        [int]$BackendPort = $BACKEND_PORT,
        [int]$FrontendPort = $FRONTEND_PORT,
        [switch]$SkipBackend,
        [switch]$SkipFrontend
    )
    
    try {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "  ZEUS-IA Application Startup" -ForegroundColor Cyan
        Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        
        $backendProcess = $null
        $frontendProcess = $null
        
        try {
            # Start Backend Server
            if (-not $SkipBackend) {
                Write-Progress -Activity "Starting ZEUS-IA" -Status "Starting Backend Server..." -PercentComplete 0
                $backendProcess = Start-BackendServer -Port $BackendPort
            } else {
                Write-Log "Skipping backend server startup" -Level INFO
            }
            
            # Start Frontend Server
            if (-not $SkipFrontend) {
                Write-Progress -Activity "Starting ZEUS-IA" -Status "Starting Frontend Server..." -PercentComplete 50
                $frontendProcess = Start-FrontendServer -Port $FrontendPort -BackendUrl "http://localhost:$BackendPort"
                
                # Open browser
                try {
                    Start-Process "http://localhost:$FrontendPort"
                    Write-Log "Opened application in default browser" -Level INFO
                } catch {
                    Write-Log "Failed to open browser: $_" -Level WARN
                }
            } else {
                Write-Log "Skipping frontend server startup" -Level INFO
            }
            
            Write-Progress -Activity "Starting ZEUS-IA" -Status "Ready" -Completed
            Write-Log "ZEUS-IA is now running. Press Ctrl+C to stop." -Level SUCCESS
            
            # Keep the script running
            try {
                $host.UI.RawUI.WindowTitle = "ZEUS-IA (Running - Press Ctrl+C to exit)"
                while ($true) {
                    Start-Sleep -Seconds 1
                }
            } catch [System.Management.Automation.Host.HostException] {
                # Handle Ctrl+C
                Write-Log "Shutting down..." -Level INFO
            }
            
        } catch {
            $errorMsg = $_.Exception.Message
            Write-Log "Error during startup: $errorMsg" -Level ERROR
            Write-Error "Error: $errorMsg"
            return 1
            
        } finally {
            # Clean up
            if ($frontendProcess -and -not $frontendProcess.HasExited) {
                Write-Log "Stopping frontend server..." -Level INFO
                try { $frontendProcess.Kill() } catch {}
            }
            
            if ($backendProcess -and -not $backendProcess.HasExited) {
                Write-Log "Stopping backend server..." -Level INFO
                try { $backendProcess.Kill() } catch {}
            }
            
            Stop-ProcessIfRunning -ProcessName "node" -Force
            Stop-ProcessIfRunning -ProcessName "python" -Force
            
            Write-Log "ZEUS-IA has been stopped" -Level INFO
        }
        
    } catch {
        Write-Log "Fatal error: $_" -Level ERROR
        return 1
    }
    
    return 0
}

# Main execution
if ($MyInvocation.InvocationName -ne '.') {
    try {
        # Parse command line arguments
        [bool]$skipBackend = $false
        [bool]$skipFrontend = $false
        
        for ($i = 0; $i -lt $args.Count; $i++) {
            if ($args[$i] -eq "--skip-backend") {
                $skipBackend = $true
            } elseif ($args[$i] -eq "--skip-frontend") {
                $skipFrontend = $true
            } elseif ($args[$i] -eq "--help" -or $args[$i] -eq "-h") {
                Write-Host "ZEUS-IA Startup Script"
                Write-Host "Usage: .\run.ps1 [options]"
                Write-Host ""
                Write-Host "Options:"
                Write-Host "  --skip-backend    Skip starting the backend server"
                Write-Host "  --skip-frontend   Skip starting the frontend server"
                Write-Host "  --help, -h        Show this help message"
                Write-Host ""
                exit 0
            }
        }
        
        # Start the application
        $exitCode = Start-ZeusApplication -SkipBackend:$skipBackend -SkipFrontend:$skipFrontend
        exit $exitCode
        
    } catch {
        Write-Error "Fatal error: $_"
        exit 1
    }
}