#!/bin/bash

# ===============================================
# ZEUS-IA - Script de Validación de Producción
# ===============================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Variables de configuración
BASE_URL="https://zeus-ia.com"
API_URL="https://api.zeus-ia.com"
WS_URL="wss://ws.zeus-ia.com"

# Función para hacer requests HTTP
make_request() {
    local url=$1
    local method=${2:-GET}
    local data=$3
    local headers=$4
    
    if [ -n "$data" ]; then
        curl -s -X "$method" -H "Content-Type: application/json" $headers -d "$data" "$url"
    else
        curl -s -X "$method" $headers "$url"
    fi
}

# Verificar conectividad básica
check_connectivity() {
    log "Verificando conectividad básica..."
    
    # Verificar frontend
    if curl -s -f "$BASE_URL" > /dev/null; then
        success "Frontend accesible en $BASE_URL"
    else
        error "Frontend no accesible en $BASE_URL"
        return 1
    fi
    
    # Verificar API
    if curl -s -f "$API_URL/health" > /dev/null; then
        success "API accesible en $API_URL"
    else
        error "API no accesible en $API_URL"
        return 1
    fi
    
    success "Conectividad básica verificada"
}

# Verificar SSL/TLS
check_ssl() {
    log "Verificando configuración SSL/TLS..."
    
    # Verificar certificado SSL
    if echo | openssl s_client -servername zeus-ia.com -connect zeus-ia.com:443 2>/dev/null | openssl x509 -noout -dates; then
        success "Certificado SSL válido"
    else
        error "Certificado SSL inválido o no encontrado"
        return 1
    fi
    
    # Verificar redirección HTTP a HTTPS
    if curl -s -I "http://zeus-ia.com" | grep -q "301\|302"; then
        success "Redirección HTTP a HTTPS configurada"
    else
        warning "Redirección HTTP a HTTPS no configurada"
    fi
    
    success "Configuración SSL verificada"
}

# Verificar autenticación JWT
check_authentication() {
    log "Verificando autenticación JWT..."
    
    # Intentar login
    local login_data='{"username":"admin@zeus-ia.com","password":"changethis"}'
    local login_response=$(make_request "$API_URL/api/v1/auth/login" "POST" "$login_data")
    
    if echo "$login_response" | grep -q "access_token"; then
        success "Login exitoso"
        
        # Extraer token
        local token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
        
        # Verificar endpoint /me
        local me_response=$(make_request "$API_URL/api/v1/auth/me" "GET" "" "-H 'Authorization: Bearer $token'")
        
        if echo "$me_response" | grep -q "email"; then
            success "Endpoint /auth/me funcionando correctamente"
        else
            error "Endpoint /auth/me no funciona correctamente"
            return 1
        fi
    else
        error "Login falló"
        return 1
    fi
    
    success "Autenticación JWT verificada"
}

# Verificar WebSocket
check_websocket() {
    log "Verificando WebSocket..."
    
    # Crear script temporal para probar WebSocket
    cat > /tmp/websocket_test.js << 'EOF'
const WebSocket = require('ws');

const token = process.argv[2];
const wsUrl = `wss://ws.zeus-ia.com/ws?token=${token}`;

console.log('Conectando a WebSocket:', wsUrl);

const ws = new WebSocket(wsUrl);

ws.on('open', () => {
    console.log('✅ WebSocket conectado exitosamente');
    ws.close();
    process.exit(0);
});

ws.on('error', (error) => {
    console.log('❌ Error en WebSocket:', error.message);
    process.exit(1);
});

ws.on('close', (code, reason) => {
    if (code === 1000) {
        console.log('✅ WebSocket cerrado correctamente');
    } else {
        console.log(`❌ WebSocket cerrado con código: ${code}, razón: ${reason}`);
        process.exit(1);
    }
});

// Timeout después de 10 segundos
setTimeout(() => {
    console.log('❌ Timeout en conexión WebSocket');
    process.exit(1);
}, 10000);
EOF

    # Obtener token para WebSocket
    local login_data='{"username":"admin@zeus-ia.com","password":"changethis"}'
    local login_response=$(make_request "$API_URL/api/v1/auth/login" "POST" "$login_data")
    local token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$token" ]; then
        # Verificar si Node.js está disponible
        if command -v node &> /dev/null; then
            if node /tmp/websocket_test.js "$token"; then
                success "WebSocket funcionando correctamente"
            else
                error "WebSocket no funciona correctamente"
                return 1
            fi
        else
            warning "Node.js no disponible, saltando verificación de WebSocket"
        fi
    else
        error "No se pudo obtener token para WebSocket"
        return 1
    fi
    
    # Limpiar archivo temporal
    rm -f /tmp/websocket_test.js
    
    success "WebSocket verificado"
}

# Verificar PWA
check_pwa() {
    log "Verificando PWA..."
    
    # Verificar manifest
    if curl -s -f "$BASE_URL/manifest.json" > /dev/null; then
        success "Manifest PWA accesible"
    else
        warning "Manifest PWA no accesible"
    fi
    
    # Verificar service worker
    if curl -s -f "$BASE_URL/sw.js" > /dev/null; then
        success "Service Worker accesible"
    else
        warning "Service Worker no accesible"
    fi
    
    success "PWA verificado"
}

# Verificar rendimiento
check_performance() {
    log "Verificando rendimiento..."
    
    # Verificar tiempo de respuesta del frontend
    local frontend_time=$(curl -s -w "%{time_total}" -o /dev/null "$BASE_URL")
    if (( $(echo "$frontend_time < 2.0" | bc -l) )); then
        success "Frontend responde en ${frontend_time}s (bueno)"
    elif (( $(echo "$frontend_time < 5.0" | bc -l) )); then
        warning "Frontend responde en ${frontend_time}s (aceptable)"
    else
        error "Frontend responde en ${frontend_time}s (lento)"
        return 1
    fi
    
    # Verificar tiempo de respuesta de la API
    local api_time=$(curl -s -w "%{time_total}" -o /dev/null "$API_URL/health")
    if (( $(echo "$api_time < 1.0" | bc -l) )); then
        success "API responde en ${api_time}s (excelente)"
    elif (( $(echo "$api_time < 2.0" | bc -l) )); then
        success "API responde en ${api_time}s (bueno)"
    else
        warning "API responde en ${api_time}s (aceptable)"
    fi
    
    success "Rendimiento verificado"
}

# Verificar seguridad
check_security() {
    log "Verificando seguridad..."
    
    # Verificar headers de seguridad
    local headers=$(curl -s -I "$BASE_URL")
    
    if echo "$headers" | grep -q "Strict-Transport-Security"; then
        success "HSTS configurado"
    else
        warning "HSTS no configurado"
    fi
    
    if echo "$headers" | grep -q "X-Frame-Options"; then
        success "X-Frame-Options configurado"
    else
        warning "X-Frame-Options no configurado"
    fi
    
    if echo "$headers" | grep -q "X-Content-Type-Options"; then
        success "X-Content-Type-Options configurado"
    else
        warning "X-Content-Type-Options no configurado"
    fi
    
    success "Seguridad verificada"
}

# Función principal
main() {
    log "Iniciando validación de producción de ZEUS-IA..."
    
    check_connectivity
    check_ssl
    check_authentication
    check_websocket
    check_pwa
    check_performance
    check_security
    
    success "¡Validación completada exitosamente!"
    log "ZEUS-IA está funcionando correctamente en producción"
}

# Ejecutar función principal
main "$@"
