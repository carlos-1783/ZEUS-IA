#!/bin/bash

# ===============================================
# ZEUS-IA - Script de Despliegue en Producción
# ===============================================

set -e

echo "🚀 Iniciando despliegue de ZEUS-IA en producción..."

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

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verificar prerequisitos
check_prerequisites() {
    log "Verificando prerequisitos..."
    
    # Verificar Docker
    if ! command -v docker &> /dev/null; then
        error "Docker no está instalado"
    fi
    
    # Verificar Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose no está instalado"
    fi
    
    # Verificar archivos de configuración
    if [ ! -f "env.production" ]; then
        error "Archivo env.production no encontrado"
    fi
    
    if [ ! -f "docker-compose.prod.yml" ]; then
        error "Archivo docker-compose.prod.yml no encontrado"
    fi
    
    success "Prerequisitos verificados"
}

# Configurar variables de entorno
setup_environment() {
    log "Configurando variables de entorno..."
    
    # Copiar archivo de entorno si no existe
    if [ ! -f ".env" ]; then
        cp env.production .env
        warning "Archivo .env creado desde env.production"
        warning "Por favor, revisa y modifica las variables según sea necesario"
    fi
    
    # Generar claves secretas si no existen
    if grep -q "CHANGE_THIS_IN_PRODUCTION" .env; then
        warning "Generando claves secretas..."
        SECRET_KEY=$(openssl rand -hex 32)
        sed -i "s/CHANGE_THIS_IN_PRODUCTION/$SECRET_KEY/" .env
        success "Claves secretas generadas"
    fi
}

# Construir imágenes Docker
build_images() {
    log "Construyendo imágenes Docker..."
    
    # Construir backend
    log "Construyendo imagen del backend..."
    docker build -t zeus-backend:latest ./backend
    
    # Construir frontend
    log "Construyendo imagen del frontend..."
    docker build -t zeus-frontend:latest ./frontend
    
    success "Imágenes construidas exitosamente"
}

# Ejecutar migraciones de base de datos
run_migrations() {
    log "Ejecutando migraciones de base de datos..."
    
    # Esperar a que la base de datos esté lista
    log "Esperando a que la base de datos esté lista..."
    docker-compose -f docker-compose.prod.yml exec -T db pg_isready -U zeus_user -d zeus_ia_prod
    
    # Ejecutar migraciones
    docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
    
    success "Migraciones ejecutadas exitosamente"
}

# Desplegar servicios
deploy_services() {
    log "Desplegando servicios..."
    
    # Detener servicios existentes
    log "Deteniendo servicios existentes..."
    docker-compose -f docker-compose.prod.yml down
    
    # Iniciar servicios en modo detached
    log "Iniciando servicios..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Esperar a que los servicios estén listos
    log "Esperando a que los servicios estén listos..."
    sleep 30
    
    success "Servicios desplegados exitosamente"
}

# Verificar salud de los servicios
health_check() {
    log "Verificando salud de los servicios..."
    
    # Verificar backend
    log "Verificando backend..."
    if ! curl -f http://localhost:8000/health; then
        error "Backend no está respondiendo"
    fi
    
    # Verificar frontend
    log "Verificando frontend..."
    if ! curl -f http://localhost/; then
        error "Frontend no está respondiendo"
    fi
    
    # Verificar base de datos
    log "Verificando base de datos..."
    if ! docker-compose -f docker-compose.prod.yml exec -T db pg_isready -U zeus_user -d zeus_ia_prod; then
        error "Base de datos no está respondiendo"
    fi
    
    success "Todos los servicios están funcionando correctamente"
}

# Configurar SSL con Let's Encrypt
setup_ssl() {
    log "Configurando SSL con Let's Encrypt..."
    
    # Verificar si ya existen certificados
    if [ -d "./letsencrypt/live/zeusia.app" ]; then
        warning "Certificados SSL ya existen, saltando configuración"
        return
    fi
    
    # Detener nginx temporalmente
    docker-compose -f docker-compose.prod.yml stop nginx
    
    # Obtener certificados
    log "Obteniendo certificados SSL..."
    docker run -it --rm \
        -v "$(pwd)/letsencrypt:/etc/letsencrypt" \
        -v "$(pwd)/letsencrypt:/var/lib/letsencrypt" \
        -v "$(pwd)/public_html:/var/www/certbot" \
        certbot/certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email admin@zeusia.app \
        --agree-tos \
        --no-eff-email \
        -d zeusia.app \
        -d www.zeusia.app
    
    # Reiniciar nginx
    docker-compose -f docker-compose.prod.yml up -d nginx
    
    success "SSL configurado exitosamente"
}

# Función principal
main() {
    log "Iniciando proceso de despliegue..."
    
    check_prerequisites
    setup_environment
    build_images
    deploy_services
    run_migrations
    health_check
    
    log "Configurando SSL (esto puede tomar varios minutos)..."
    setup_ssl
    
    success "🎉 Despliegue completado exitosamente!"
    log "Frontend: https://zeusia.app"
    log "API: https://api.zeusia.app"
    log "Dashboard: https://zeusia.app/admin"
    
    # Mostrar logs de los servicios
    log "Mostrando logs de los servicios..."
    docker-compose -f docker-compose.prod.yml logs --tail=50
}

# Ejecutar función principal
main "$@"