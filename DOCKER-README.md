# 🐳 ZEUS-IA - Configuración Docker para Producción

## 📋 Resumen de Configuración

Este proyecto está completamente configurado para producción usando Docker con las siguientes características:

### ✅ **Backend (FastAPI + Gunicorn)**
- **Multi-stage Dockerfile** con etapas de desarrollo y producción
- **Gunicorn** con workers optimizados para producción
- **Usuario no-root** para seguridad
- **Health checks** integrados
- **Logs estructurados** y rotación automática
- **Variables de entorno** seguras para producción

### ✅ **Frontend (Vue.js + Vite)**
- **Build optimizado** para producción
- **Nginx** como servidor web
- **PWA** configurado sin warnings
- **Compresión gzip** habilitada
- **Cache headers** optimizados
- **Service Worker** funcionando correctamente

### ✅ **WebSockets**
- **Proxy WebSocket** configurado en Nginx
- **Headers de Upgrade** y Connection correctos
- **Autenticación JWT** en WebSocket
- **Timeouts** optimizados para conexiones persistentes

### ✅ **Proxy y SSL**
- **Nginx** como reverse proxy
- **Let's Encrypt** para SSL automático
- **Redirección HTTP → HTTPS**
- **Headers de seguridad** (HSTS, CSP, etc.)
- **Rate limiting** configurado

### ✅ **Base de Datos y Cache**
- **PostgreSQL 15** para producción
- **Redis 7** para cache y sesiones
- **Volúmenes persistentes** para datos
- **Health checks** para todos los servicios

## 🚀 Comandos de Despliegue

### Desarrollo Local
```bash
# Iniciar en modo desarrollo
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```

### Producción
```bash
# Desplegar en producción
./scripts/deploy-production.sh

# Validar despliegue
./scripts/validate-production.sh

# Usar Traefik (alternativa a Nginx)
docker-compose -f docker-compose.traefik.yml up -d
```

## 📁 Estructura de Archivos

```
ZEUS-IA/
├── backend/
│   ├── Dockerfile              # Multi-stage para dev/prod
│   ├── gunicorn.conf.py        # Configuración Gunicorn
│   └── requirements.txt        # Dependencias Python
├── frontend/
│   ├── Dockerfile              # Build optimizado para prod
│   ├── Dockerfile.dev          # Para desarrollo
│   └── nginx.conf              # Configuración Nginx frontend
├── nginx/
│   ├── nginx-prod.conf         # Nginx para producción
│   └── nginx-dev.conf          # Nginx para desarrollo
├── scripts/
│   ├── deploy-production.sh    # Script de despliegue
│   ├── deploy-local.sh         # Script para desarrollo
│   ├── validate-production.sh  # Validación de producción
│   └── init-db.sql            # Inicialización BD
├── docker-compose.yml          # Desarrollo
├── docker-compose.prod.yml     # Producción
├── docker-compose.traefik.yml  # Con Traefik
├── .env.development           # Variables desarrollo
└── .env.production            # Variables producción
```

## 🔧 Configuración de Servicios

### Backend
- **Puerto**: 8000
- **Workers**: CPU cores × 2 + 1
- **Memoria**: 2GB límite, 1GB reservado
- **Health check**: `/health`

### Frontend
- **Puerto**: 80 (interno)
- **Memoria**: 512MB límite, 256MB reservado
- **Health check**: `/`

### Base de Datos
- **PostgreSQL 15** con Alpine
- **Memoria**: 1GB límite, 512MB reservado
- **Volumen**: `postgres_prod_data`

### Redis
- **Puerto**: 6379 (interno)
- **Memoria**: 512MB límite, 256MB reservado
- **Volumen**: `redis_prod_data`

### Nginx
- **Puertos**: 80, 443
- **Memoria**: 512MB límite, 256MB reservado
- **SSL**: Let's Encrypt automático

## 🔒 Seguridad

### Headers de Seguridad
- **HSTS**: 1 año con preload
- **CSP**: Política estricta configurada
- **X-Frame-Options**: DENY
- **X-Content-Type-Options**: nosniff
- **X-XSS-Protection**: 1; mode=block

### Rate Limiting
- **API**: 10 requests/segundo
- **Login**: 5 requests/minuto
- **Burst**: 20 requests

### SSL/TLS
- **Protocolos**: TLSv1.2, TLSv1.3
- **Ciphers**: ECDHE-RSA-AES256-GCM-SHA512
- **OCSP Stapling**: Habilitado

## 📊 Monitoreo

### Health Checks
Todos los servicios tienen health checks configurados:
- **Backend**: `curl -f http://localhost:8000/health`
- **Frontend**: `curl -f http://localhost/`
- **PostgreSQL**: `pg_isready`
- **Redis**: `redis-cli ping`

### Logs
- **Ubicación**: `./backend/logs/`, `./nginx/logs/`
- **Formato**: JSON estructurado
- **Rotación**: Automática

### Métricas
- **Prometheus**: Habilitado (opcional)
- **StatsD**: Configurado
- **Dashboard**: Disponible en Traefik

## 🌐 URLs de Acceso

### Producción
- **Frontend**: https://zeus-ia.com
- **API**: https://api.zeus-ia.com
- **WebSocket**: wss://ws.zeus-ia.com
- **Traefik Dashboard**: https://traefik.zeus-ia.com:8080

### Desarrollo
- **Frontend**: http://localhost:5173
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🔄 Comandos Útiles

### Gestión de Servicios
```bash
# Ver estado de servicios
docker-compose ps

# Reiniciar un servicio
docker-compose restart backend

# Ver logs de un servicio
docker-compose logs -f backend

# Ejecutar comando en contenedor
docker-compose exec backend python manage.py migrate
```

### Base de Datos
```bash
# Backup de base de datos
docker-compose exec db pg_dump -U zeus_user zeus_ia_prod > backup.sql

# Restaurar backup
docker-compose exec -T db psql -U zeus_user zeus_ia_prod < backup.sql
```

### SSL
```bash
# Renovar certificados
docker-compose exec nginx certbot renew

# Verificar certificados
openssl s_client -connect zeus-ia.com:443 -servername zeus-ia.com
```

## 🚨 Troubleshooting

### Problemas Comunes

1. **Puerto 80/443 ocupado**
   ```bash
   sudo netstat -tulpn | grep :80
   sudo systemctl stop apache2  # o nginx
   ```

2. **Certificados SSL no válidos**
   ```bash
   docker-compose down
   sudo rm -rf letsencrypt/
   ./scripts/deploy-production.sh
   ```

3. **WebSocket no conecta**
   - Verificar headers de Upgrade
   - Comprobar autenticación JWT
   - Revisar logs de Nginx

4. **Base de datos no inicia**
   ```bash
   docker-compose logs db
   docker volume rm zeus-ia_postgres_prod_data
   ```

### Logs Importantes
```bash
# Logs de aplicación
docker-compose logs -f backend

# Logs de Nginx
docker-compose logs -f nginx

# Logs de base de datos
docker-compose logs -f db
```

## 📈 Escalabilidad

### Horizontal Scaling
```bash
# Escalar backend
docker-compose up -d --scale backend=3

# Load balancer automático con Nginx
```

### Vertical Scaling
Editar `docker-compose.prod.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 4G  # Aumentar memoria
    reservations:
      memory: 2G
```

## 🎯 Próximos Pasos

1. **Configurar dominio** en DNS
2. **Ejecutar script de despliegue**
3. **Validar funcionamiento**
4. **Configurar monitoreo**
5. **Implementar backups automáticos**

---

**¡ZEUS-IA está listo para producción! 🚀**
