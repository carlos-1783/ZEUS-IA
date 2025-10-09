#!/bin/bash

# Script para configurar el backend de ZEUS-IA en producción
# ==========================================================

set -e

echo "🚀 Configurando backend ZEUS-IA para producción..."

# Variables
APP_DIR="/opt/zeus-ia"
VENV_DIR="/opt/zeus-ia/venv"
SERVICE_USER="zeus-ia"
LOG_DIR="/var/log/zeus-ia"

# Verificar que el script se ejecute como root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Este script debe ejecutarse como root (sudo)"
    exit 1
fi

# Crear usuario del sistema
echo "👤 Creando usuario del sistema..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home-dir $APP_DIR --create-home $SERVICE_USER
    echo "✅ Usuario $SERVICE_USER creado"
else
    echo "ℹ️ Usuario $SERVICE_USER ya existe"
fi

# Crear directorios
echo "📁 Creando directorios..."
mkdir -p $APP_DIR
mkdir -p $LOG_DIR
mkdir -p /var/run/zeus-ia

# Permisos
chown -R $SERVICE_USER:$SERVICE_USER $APP_DIR
chown -R $SERVICE_USER:$SERVICE_USER $LOG_DIR
chmod 755 $LOG_DIR

# Instalar dependencias del sistema
echo "📦 Instalando dependencias del sistema..."
apt update
apt install -y python3 python3-pip python3-venv python3-dev build-essential
apt install -y postgresql-client libpq-dev
apt install -y redis-tools
apt install -y supervisor

# Crear entorno virtual
echo "🐍 Creando entorno virtual de Python..."
sudo -u $SERVICE_USER python3 -m venv $VENV_DIR
sudo -u $SERVICE_USER $VENV_DIR/bin/pip install --upgrade pip

# Instalar dependencias de Python
echo "📦 Instalando dependencias de Python..."
sudo -u $SERVICE_USER $VENV_DIR/bin/pip install -r $APP_DIR/requirements.txt

# Copiar archivos de la aplicación
echo "📋 Copiando archivos de la aplicación..."
cp -r /path/to/zeus-ia/backend/* $APP_DIR/
chown -R $SERVICE_USER:$SERVICE_USER $APP_DIR

# Crear archivo de configuración de entorno
echo "⚙️ Configurando variables de entorno..."
cat > $APP_DIR/.env << EOF
# Configuración de Producción ZEUS-IA
DATABASE_URL=postgresql://zeus_user:zeus_secure_password_2024@localhost:5432/zeus_ia_prod
SECRET_KEY=zeus_ia_super_secure_secret_key_2024_production_ultra_strong_256_bits_minimum
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BACKEND_CORS_ORIGINS=https://zeus-ia.com,https://www.zeus-ia.com,https://app.zeus-ia.com
ALLOWED_HOSTS=zeus-ia.com,www.zeus-ia.com,app.zeus-ia.com,localhost,127.0.0.1
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
BCRYPT_ROUNDS=12
API_V1_STR=/api/v1
PROJECT_NAME=ZEUS-IA
VERSION=1.0.0
WEBSOCKET_MAX_CONNECTIONS=1000
RATE_LIMIT_PER_MINUTE=60
EOF

chown $SERVICE_USER:$SERVICE_USER $APP_DIR/.env
chmod 600 $APP_DIR/.env

# Crear archivo de servicio systemd
echo "🔧 Configurando servicio systemd..."
cat > /etc/systemd/system/zeus-ia.service << EOF
[Unit]
Description=ZEUS-IA Backend API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=exec
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/gunicorn -c gunicorn.conf.py app.main:app
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=zeus-ia

# Configuración de seguridad
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR $LOG_DIR /var/run/zeus-ia
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

# Límites de recursos
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

# Crear configuración de supervisor (alternativa)
echo "🔧 Configurando supervisor..."
cat > /etc/supervisor/conf.d/zeus-ia.conf << EOF
[program:zeus-ia]
command=$VENV_DIR/bin/gunicorn -c gunicorn.conf.py app.main:app
directory=$APP_DIR
user=$SERVICE_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/supervisor.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=PATH="$VENV_DIR/bin",ENVIRONMENT="production"
EOF

# Recargar configuración de supervisor
supervisorctl reread
supervisorctl update

# Habilitar y iniciar servicio
echo "🚀 Iniciando servicio..."
systemctl daemon-reload
systemctl enable zeus-ia
systemctl start zeus-ia

# Verificar estado
echo "🔍 Verificando estado del servicio..."
sleep 5
systemctl status zeus-ia --no-pager -l

# Verificar que el puerto esté escuchando
echo "🔍 Verificando que el puerto 8000 esté escuchando..."
if netstat -tlnp | grep :8000; then
    echo "✅ Backend escuchando en puerto 8000"
else
    echo "❌ Error: Backend no está escuchando en puerto 8000"
    exit 1
fi

# Probar endpoint de health
echo "🔍 Probando endpoint de health..."
if curl -f http://localhost:8000/health; then
    echo "✅ Endpoint de health respondiendo correctamente"
else
    echo "❌ Error: Endpoint de health no responde"
    exit 1
fi

echo ""
echo "🎉 ¡Backend ZEUS-IA configurado exitosamente!"
echo ""
echo "📋 Resumen:"
echo "   - Usuario: $SERVICE_USER"
echo "   - Directorio: $APP_DIR"
echo "   - Entorno virtual: $VENV_DIR"
echo "   - Logs: $LOG_DIR"
echo "   - Servicio: zeus-ia.service"
echo "   - Puerto: 8000"
echo ""
echo "🔧 Comandos útiles:"
echo "   - Ver logs: journalctl -u zeus-ia -f"
echo "   - Reiniciar: systemctl restart zeus-ia"
echo "   - Estado: systemctl status zeus-ia"
echo "   - Supervisor: supervisorctl status zeus-ia"
echo ""
echo "⚠️  Recuerda:"
echo "   1. Configurar la base de datos PostgreSQL"
echo "   2. Configurar Redis"
echo "   3. Actualizar las variables de entorno según tu configuración"
echo "   4. Probar la conexión con el frontend"
echo ""
