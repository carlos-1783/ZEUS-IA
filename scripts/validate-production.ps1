# ===============================================
# ZEUS-IA - Script de Validación de Producción
# ===============================================

param(
    [Parameter(Mandatory=$false)]
    [string]$BaseUrl = "https://zeusia.app",
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://api.zeusia.app",
    
    [Parameter(Mandatory=$false)]
    [switch]$FullTest = $false
)

# Colores para output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"
$White = "White"

function Write-Log {
    param([string]$Message, [string]$Color = $White)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-Log "✅ $Message" $Green
}

function Write-Error {
    param([string]$Message)
    Write-Log "❌ $Message" $Red
}

function Write-Warning {
    param([string]$Message)
    Write-Log "⚠️  $Message" $Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Log "ℹ️  $Message" $Blue
}

# Función para hacer peticiones HTTP
function Invoke-TestRequest {
    param(
        [string]$Url,
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [string]$Body = $null,
        [int]$TimeoutSeconds = 30
    )
    
    try {
        $params = @{
            Uri = $Url
            Method = $Method
            Headers = $Headers
            TimeoutSec = $TimeoutSeconds
        }
        
        if ($Body) {
            $params.Body = $Body
        }
        
        $response = Invoke-WebRequest @params
        return @{
            Success = $true
            StatusCode = $response.StatusCode
            Response = $response.Content
            Headers = $response.Headers
        }
    }
    catch {
        return @{
            Success = $false
            Error = $_.Exception.Message
            StatusCode = $_.Exception.Response.StatusCode
        }
    }
}

# Verificar conectividad básica
function Test-Connectivity {
    Write-Info "Verificando conectividad básica..."
    
    # Test frontend
    Write-Info "Probando frontend: $BaseUrl"
    $frontendTest = Invoke-TestRequest -Url $BaseUrl
    if ($frontendTest.Success) {
        Write-Success "Frontend accesible (Status: $($frontendTest.StatusCode))"
    } else {
        Write-Error "Frontend no accesible: $($frontendTest.Error)"
        return $false
    }
    
    # Test API
    Write-Info "Probando API: $ApiUrl"
    $apiTest = Invoke-TestRequest -Url "$ApiUrl/health"
    if ($apiTest.Success) {
        Write-Success "API accesible (Status: $($apiTest.StatusCode))"
    } else {
        Write-Error "API no accesible: $($apiTest.Error)"
        return $false
    }
    
    return $true
}

# Verificar endpoints de la API
function Test-ApiEndpoints {
    Write-Info "Verificando endpoints de la API..."
    
    $endpoints = @(
        @{ Path = "/health"; Method = "GET"; ExpectedStatus = 200 },
        @{ Path = "/api/v1/health"; Method = "GET"; ExpectedStatus = 200 },
        @{ Path = "/api/v1/auth/register"; Method = "POST"; ExpectedStatus = 422 }, # 422 es esperado sin datos
        @{ Path = "/api/v1/auth/login"; Method = "POST"; ExpectedStatus = 422 }, # 422 es esperado sin datos
        @{ Path = "/api/v1/users/me"; Method = "GET"; ExpectedStatus = 401 } # 401 es esperado sin token
    )
    
    $allPassed = $true
    
    foreach ($endpoint in $endpoints) {
        $url = "$ApiUrl$($endpoint.Path)"
        Write-Info "Probando: $($endpoint.Method) $url"
        
        $test = Invoke-TestRequest -Url $url -Method $endpoint.Method
        
        if ($test.Success -and $test.StatusCode -eq $endpoint.ExpectedStatus) {
            Write-Success "✅ $($endpoint.Method) $($endpoint.Path) - Status: $($test.StatusCode)"
        } else {
            Write-Warning "⚠️  $($endpoint.Method) $($endpoint.Path) - Status: $($test.StatusCode) (Esperado: $($endpoint.ExpectedStatus))"
            if (-not $test.Success) {
                Write-Error "Error: $($test.Error)"
                $allPassed = $false
            }
        }
    }
    
    return $allPassed
}

# Verificar SSL/TLS
function Test-SslSecurity {
    Write-Info "Verificando seguridad SSL/TLS..."
    
    $sslTest = @{
        "Frontend SSL" = $BaseUrl
        "API SSL" = $ApiUrl
    }
    
    $allSecure = $true
    
    foreach ($service in $sslTest.GetEnumerator()) {
        try {
            $request = [System.Net.WebRequest]::Create($service.Value)
            $request.Method = "HEAD"
            $request.Timeout = 10000
            
            $response = $request.GetResponse()
            $response.Close()
            
            if ($service.Value.StartsWith("https://")) {
                Write-Success "✅ $($service.Key) - HTTPS configurado correctamente"
            } else {
                Write-Warning "⚠️  $($service.Key) - No está usando HTTPS"
                $allSecure = $false
            }
        }
        catch {
            Write-Error "❌ $($service.Key) - Error de conexión: $($_.Exception.Message)"
            $allSecure = $false
        }
    }
    
    return $allSecure
}

# Verificar headers de seguridad
function Test-SecurityHeaders {
    Write-Info "Verificando headers de seguridad..."
    
    $frontendResponse = Invoke-TestRequest -Url $BaseUrl
    $apiResponse = Invoke-TestRequest -Url "$ApiUrl/health"
    
    $securityHeaders = @(
        "X-Frame-Options",
        "X-Content-Type-Options",
        "X-XSS-Protection",
        "Strict-Transport-Security"
    )
    
    $allSecure = $true
    
    foreach ($header in $securityHeaders) {
        if ($frontendResponse.Headers.ContainsKey($header)) {
            Write-Success "✅ Frontend - $header presente"
        } else {
            Write-Warning "⚠️  Frontend - $header no encontrado"
            $allSecure = $false
        }
        
        if ($apiResponse.Headers.ContainsKey($header)) {
            Write-Success "✅ API - $header presente"
        } else {
            Write-Warning "⚠️  API - $header no encontrado"
            $allSecure = $false
        }
    }
    
    return $allSecure
}

# Verificar PWA
function Test-PwaFeatures {
    Write-Info "Verificando características PWA..."
    
    # Verificar manifest
    $manifestTest = Invoke-TestRequest -Url "$BaseUrl/manifest.webmanifest"
    if ($manifestTest.Success) {
        Write-Success "✅ Web App Manifest accesible"
        
        try {
            $manifest = $manifestTest.Response | ConvertFrom-Json
            if ($manifest.name -and $manifest.short_name) {
                Write-Success "✅ Manifest válido"
            } else {
                Write-Warning "⚠️  Manifest incompleto"
            }
        }
        catch {
            Write-Warning "⚠️  Error al parsear manifest"
        }
    } else {
        Write-Warning "⚠️  Web App Manifest no accesible"
    }
    
    # Verificar service worker (solo en producción)
    $swTest = Invoke-TestRequest -Url "$BaseUrl/sw.js"
    if ($swTest.Success) {
        Write-Success "✅ Service Worker disponible"
    } else {
        Write-Warning "⚠️  Service Worker no encontrado"
    }
    
    return $true
}

# Verificar rendimiento
function Test-Performance {
    Write-Info "Verificando rendimiento..."
    
    $startTime = Get-Date
    
    # Test frontend
    $frontendTest = Invoke-TestRequest -Url $BaseUrl
    $frontendTime = (Get-Date) - $startTime
    
    if ($frontendTest.Success) {
        if ($frontendTime.TotalSeconds -lt 3) {
            Write-Success "✅ Frontend carga rápida: $([math]::Round($frontendTime.TotalSeconds, 2))s"
        } else {
            Write-Warning "⚠️  Frontend carga lenta: $([math]::Round($frontendTime.TotalSeconds, 2))s"
        }
    } else {
        Write-Warning "⚠️  Frontend no accesible para test de rendimiento"
    }
    
    # Test API
    $startTime = Get-Date
    $apiTest = Invoke-TestRequest -Url "$ApiUrl/health"
    $apiTime = (Get-Date) - $startTime
    
    if ($apiTest.Success) {
        if ($apiTime.TotalSeconds -lt 1) {
            Write-Success "✅ API respuesta rápida: $([math]::Round($apiTime.TotalSeconds, 2))s"
        } else {
            Write-Warning "⚠️  API respuesta lenta: $([math]::Round($apiTime.TotalSeconds, 2))s"
        }
    } else {
        Write-Warning "⚠️  API no accesible para test de rendimiento"
    }
    
    return $true
}

# Test completo de autenticación
function Test-Authentication {
    Write-Info "Verificando flujo de autenticación..."
    
    # Test registro
    $registerData = @{
        username = "testuser_$(Get-Date -Format 'yyyyMMddHHmmss')"
        email = "test_$(Get-Date -Format 'yyyyMMddHHmmss')@example.com"
        password = "TestPassword123!"
    } | ConvertTo-Json
    
    $registerHeaders = @{
        "Content-Type" = "application/json"
    }
    
    $registerTest = Invoke-TestRequest -Url "$ApiUrl/api/v1/auth/register" -Method "POST" -Headers $registerHeaders -Body $registerData
    if ($registerTest.Success -and $registerTest.StatusCode -eq 201) {
        Write-Success "✅ Registro de usuario funciona"
        
        # Test login
        $loginData = @{
            username = $registerData.username
            password = "TestPassword123!"
        } | ConvertTo-Json
        
        $loginTest = Invoke-TestRequest -Url "$ApiUrl/api/v1/auth/login" -Method "POST" -Headers $registerHeaders -Body $loginData
        if ($loginTest.Success -and $loginTest.StatusCode -eq 200) {
            Write-Success "✅ Login de usuario funciona"
            
            try {
                $loginResponse = $loginTest.Response | ConvertFrom-Json
                if ($loginResponse.access_token) {
                    Write-Success "✅ Token JWT generado correctamente"
                    
                    # Test endpoint protegido
                    $authHeaders = @{
                        "Authorization" = "Bearer $($loginResponse.access_token)"
                    }
                    
                    $protectedTest = Invoke-TestRequest -Url "$ApiUrl/api/v1/users/me" -Headers $authHeaders
                    if ($protectedTest.Success -and $protectedTest.StatusCode -eq 200) {
                        Write-Success "✅ Endpoint protegido accesible con token"
                        return $true
                    } else {
                        Write-Warning "⚠️  Endpoint protegido no accesible"
                    }
                } else {
                    Write-Warning "⚠️  Token JWT no generado"
                }
            }
            catch {
                Write-Warning "⚠️  Error al parsear respuesta de login"
            }
        } else {
            Write-Warning "⚠️  Login de usuario no funciona"
        }
    } else {
        Write-Warning "⚠️  Registro de usuario no funciona"
    }
    
    return $false
}

# Función principal
function Main {
    Write-Log "🔍 Iniciando validación de producción ZEUS-IA" $Blue
    Write-Info "Frontend: $BaseUrl"
    Write-Info "API: $ApiUrl"
    
    $allTestsPassed = $true
    
    # Tests básicos
    if (-not (Test-Connectivity)) {
        Write-Error "❌ Tests de conectividad fallaron"
        $allTestsPassed = $false
    }
    
    if (-not (Test-ApiEndpoints)) {
        Write-Warning "⚠️  Algunos endpoints de API fallaron"
    }
    
    if (-not (Test-SslSecurity)) {
        Write-Warning "⚠️  Problemas de seguridad SSL detectados"
        $allTestsPassed = $false
    }
    
    if (-not (Test-SecurityHeaders)) {
        Write-Warning "⚠️  Headers de seguridad faltantes"
    }
    
    Test-PwaFeatures
    Test-Performance
    
    # Tests avanzados
    if ($FullTest) {
        if (-not (Test-Authentication)) {
            Write-Warning "⚠️  Tests de autenticación fallaron"
        }
    }
    
    # Resumen final
    Write-Log "📊 Resumen de validación:" $Blue
    if ($allTestsPassed) {
        Write-Success "🎉 ¡Todas las validaciones críticas pasaron!"
        Write-Success "✅ ZEUS-IA está listo para producción"
    } else {
        Write-Warning "⚠️  Algunas validaciones fallaron. Revisa los logs arriba."
    }
    
    Write-Info "📱 URLs de acceso:"
    Write-Info "   Frontend: $BaseUrl"
    Write-Info "   API: $ApiUrl"
    Write-Info "   Health Check: $ApiUrl/health"
    Write-Info "   Admin Panel: $BaseUrl/admin"
}

# Ejecutar función principal
Main
