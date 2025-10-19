# Script para iniciar el servidor de desarrollo del frontend
Write-Host "=== ZEUS-IA Frontend Development Server ===" -ForegroundColor Cyan

# Verificar si Node.js está instalado
try {
    $nodeVersion = node --version
    Write-Host "Node.js version: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Node.js no está instalado o no está en el PATH" -ForegroundColor Red
    exit 1
}

# Verificar si npm está instalado
try {
    $npmVersion = npm --version
    Write-Host "npm version: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: npm no está instalado o no está en el PATH" -ForegroundColor Red
    exit 1
}

# Cambiar al directorio del frontend
Set-Location $PSScriptRoot

# Verificar si node_modules existe
if (-not (Test-Path "node_modules")) {
    Write-Host "Instalando dependencias..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error al instalar dependencias" -ForegroundColor Red
        exit 1
    }
}

# Verificar si el puerto 5173 está disponible
try {
    $connection = Test-NetConnection -ComputerName localhost -Port 5173 -InformationLevel Quiet
    if ($connection) {
        Write-Host "Puerto 5173 está ocupado. Intentando puerto 5174..." -ForegroundColor Yellow
        $env:VITE_DEV_SERVER_PORT = "5174"
    }
} catch {
    Write-Host "Puerto 5173 disponible" -ForegroundColor Green
}

# Iniciar el servidor de desarrollo
Write-Host "Iniciando servidor de desarrollo..." -ForegroundColor Yellow
Write-Host "URL: http://localhost:5173 (o puerto alternativo si 5173 está ocupado)" -ForegroundColor Cyan
Write-Host "Presione Ctrl+C para detener el servidor" -ForegroundColor Yellow

npm run dev
