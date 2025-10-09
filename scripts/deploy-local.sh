#!/bin/bash

# ===============================================
# ZEUS-IA - Script de Despliegue Local
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

# Verificar que Docker esté instalado
check_docker() {
    log "Verificando instalación de Docker..."
    if ! command -v docker &> /dev/null; then
        error "Docker no está instalado. Por favor instala Docker primero."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose no está instalado. Por favor instala Docker Compose primero."
        exit 1
    fi
    
    success "Docker y Docker Compose están instalados"
}

# Verificar archivos de configuración
check_config() {
    log "Verificando archivos de configuración..."
    
    if [ ! -f ".env.development" ]; then
        error "Archivo .env.development no encontrado"
        exit 1
    fi
    
    if [ ! -f "docker-compose.yml" ]; then
        error "Archivo docker-compose.yml no encontrado"
        exit 1
    fi
    
    success "Archivos de configuración encontrados"
}

# Limpiar contenedores y volúmenes existentes
cleanup() {
    log "Limpiando contenedores y volúmenes existentes..."
    
    # Detener y eliminar contenedores
    docker-compose down -v --remove-orphans
    
    # Limpiar imágenes no utilizadas
    docker image prune -f
    
    success "Limpieza completada"
}

# Construir imágenes
build_images() {
    log "Construyendo imágenes Docker..."
    
    # Construir backend
    log "Construyendo backend..."
    docker-compose build backend
    
    # Construir frontend
    log "Construyendo frontend..."
    docker-compose build frontend
    
    success "Imágenes construidas"
}

# Iniciar servicios
start_services() {
    log "Iniciando servicios..."
    
    # Iniciar servicios en background
    docker-compose up -d
    
    success "Servicios iniciados"
}

# Verificar salud de los servicios
check_health() {
    log "Verificando salud de los servicios..."
    
    # Esperar a que los servicios estén listos
    sleep 15
    
    # Verificar backend
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        success "Backend está funcionando en http://localhost:8000"
    else
        warning "Backend no está respondiendo aún, esperando..."
        sleep 10
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            success "Backend está funcionando en http://localhost:8000"
        else
            error "Backend no está respondiendo"
            return 1
        fi
    fi
    
    # Verificar frontend
    if curl -f http://localhost:5173 > /dev/null 2>&1; then
        success "Frontend está funcionando en http://localhost:5173"
    else
        warning "Frontend no está respondiendo aún, esperando..."
        sleep 10
        if curl -f http://localhost:5173 > /dev/null 2>&1; then
            success "Frontend está funcionando en http://localhost:5173"
        else
            error "Frontend no está respondiendo"
            return 1
        fi
    fi
    
    success "Todos los servicios están funcionando"
}

# Mostrar información de acceso
show_info() {
    log "Información de acceso:"
    echo ""
    echo -e "${GREEN}🚀 ZEUS-IA está funcionando localmente:${NC}"
    echo -e "  • Frontend: ${BLUE}http://localhost:5173${NC}"
    echo -e "  • Backend API: ${BLUE}http://localhost:8000${NC}"
    echo -e "  • API Docs: ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "  • WebSocket: ${BLUE}ws://localhost:8000/ws${NC}"
    echo ""
    echo -e "${YELLOW}Comandos útiles:${NC}"
    echo -e "  • Ver logs: ${BLUE}docker-compose logs -f${NC}"
    echo -e "  • Detener: ${BLUE}docker-compose down${NC}"
    echo -e "  • Reiniciar: ${BLUE}docker-compose restart${NC}"
    echo ""
}

# Función principal
main() {
    log "Iniciando despliegue local de ZEUS-IA..."
    
    check_docker
    check_config
    cleanup
    build_images
    start_services
    check_health
    show_info
    
    success "¡Despliegue local completado exitosamente!"
}

# Ejecutar función principal
main "$@"
