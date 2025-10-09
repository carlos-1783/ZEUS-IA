#!/bin/bash

# Script para configurar SSL con Let's Encrypt para ZEUS-IA
# =========================================================

set -e

echo "🔐 Configurando SSL con Let's Encrypt para ZEUS-IA..."

# Variables
DOMAIN="zeus-ia.com"
EMAIL="admin@zeus-ia.com"
NGINX_CONFIG="/etc/nginx/sites-available/zeus-ia"
NGINX_ENABLED="/etc/nginx/sites-enabled/zeus-ia"

# Verificar que el script se ejecute como root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Este script debe ejecutarse como root (sudo)"
    exit 1
fi

# Actualizar sistema
echo "📦 Actualizando sistema..."
apt update && apt upgrade -y

# Instalar Nginx si no está instalado
if ! command -v nginx &> /dev/null; then
    echo "📦 Instalando Nginx..."
    apt install nginx -y
    systemctl enable nginx
    systemctl start nginx
fi

# Instalar Certbot
echo "📦 Instalando Certbot..."
apt install certbot python3-certbot-nginx -y

# Crear configuración temporal de Nginx para obtener certificados
echo "⚙️ Creando configuración temporal de Nginx..."
cat > /etc/nginx/sites-available/zeus-ia-temp << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN app.$DOMAIN;
    
    location / {
        return 200 'ZEUS-IA - Configurando SSL...';
        add_header Content-Type text/plain;
    }
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
EOF

# Habilitar configuración temporal
ln -sf /etc/nginx/sites-available/zeus-ia-temp /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Obtener certificados SSL
echo "🔐 Obteniendo certificados SSL..."
certbot certonly \
    --webroot \
    --webroot-path=/var/www/html \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --domains $DOMAIN,www.$DOMAIN,app.$DOMAIN

# Verificar que los certificados se crearon
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "❌ Error: No se pudieron obtener los certificados SSL"
    exit 1
fi

echo "✅ Certificados SSL obtenidos exitosamente"

# Crear directorio para archivos estáticos
echo "📁 Creando directorio para archivos estáticos..."
mkdir -p /var/www/zeus-ia/dist
chown -R www-data:www-data /var/www/zeus-ia
chmod -R 755 /var/www/zeus-ia

# Copiar archivos del frontend
echo "📋 Copiando archivos del frontend..."
cp -r /path/to/zeus-ia/frontend/dist/* /var/www/zeus-ia/dist/

# Reemplazar configuración temporal con la definitiva
echo "⚙️ Configurando Nginx definitivo..."
cp /path/to/zeus-ia/nginx/zeus-ia.conf /etc/nginx/sites-available/zeus-ia

# Habilitar configuración definitiva
rm -f /etc/nginx/sites-enabled/zeus-ia-temp
ln -sf /etc/nginx/sites-available/zeus-ia /etc/nginx/sites-enabled/

# Verificar configuración de Nginx
echo "🔍 Verificando configuración de Nginx..."
nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configuración de Nginx válida"
    systemctl reload nginx
else
    echo "❌ Error en la configuración de Nginx"
    exit 1
fi

# Configurar renovación automática
echo "🔄 Configurando renovación automática..."
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --reload-hook 'systemctl reload nginx'") | crontab -

# Configurar firewall
echo "🔥 Configurando firewall..."
ufw allow 'Nginx Full'
ufw allow ssh
ufw --force enable

# Verificar estado de los servicios
echo "🔍 Verificando estado de los servicios..."
systemctl status nginx --no-pager -l
systemctl status certbot.timer --no-pager -l

echo ""
echo "🎉 ¡Configuración SSL completada exitosamente!"
echo ""
echo "📋 Resumen:"
echo "   - Dominio: $DOMAIN"
echo "   - Certificados: /etc/letsencrypt/live/$DOMAIN/"
echo "   - Nginx config: /etc/nginx/sites-available/zeus-ia"
echo "   - Archivos estáticos: /var/www/zeus-ia/dist/"
echo "   - Renovación automática: Configurada"
echo ""
echo "🌐 Tu sitio estará disponible en: https://$DOMAIN"
echo ""
echo "⚠️  Recuerda:"
echo "   1. Configurar el backend FastAPI en el puerto 8000"
echo "   2. Actualizar las variables de entorno del backend"
echo "   3. Probar la conexión HTTPS y WebSocket"
echo ""
