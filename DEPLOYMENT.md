# Guía de Despliegue en Producción - ZEUS-IA

Esta guía proporciona instrucciones detalladas para desplegar la aplicación ZEUS-IA en un entorno de producción.

## Requisitos Previos

- Docker y Docker Compose instalados en el servidor
- Un dominio configurado y apuntando a la IP del servidor
- Acceso SSH al servidor
- Certificados SSL (pueden generarse con Let's Encrypt)

## Configuración Inicial

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/tu-usuario/zeus-ia.git
   cd zeus-ia
   ```

2. **Configurar variables de entorno**
   - Copiar el archivo de ejemplo `.env.production` a `.env`
   - Editar el archivo `.env` con tus configuraciones reales
   ```bash
   cp .env.production .env
   nano .env
   ```

3. **Configurar Nginx**
   - Editar el archivo `nginx/conf.d/zeus.conf` y reemplazar `tu-dominio.com` con tu dominio real
   - Asegurarse de que los certificados SSL estén en la ruta correcta (`/etc/letsencrypt/live/tu-dominio.com/`)

## Despliegue con Docker Compose

1. **Iniciar los servicios**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Verificar los logs**
   ```bash
   docker-compose -f docker-compose.prod.yml logs -f
   ```

3. **Ejecutar migraciones** (si es necesario)
   ```bash
   docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
   ```

## Configuración de SSL con Let's Encrypt

1. **Detener Nginx temporalmente**
   ```bash
   docker-compose -f docker-compose.prod.yml stop nginx
   ```

2. **Obtener certificados**
   ```bash
   docker run -it --rm \
     -v /etc/letsencrypt:/etc/letsencrypt \
     -v /var/lib/letsencrypt:/var/lib/letsencrypt \
     -v /var/www/certbot:/var/www/certbot \
     certbot/certbot certonly \
     --standalone \
     --preferred-challenges http \
     -d tu-dominio.com -d www.tu-dominio.com \
     --email tu-email@ejemplo.com \
     --agree-tos \
     --non-interactive \
     --keep-until-expiring
   ```

3. **Reiniciar Nginx**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d nginx
   ```

## Tareas de Mantenimiento

### Actualizar la aplicación

```bash
git pull
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d --no-deps
```

### Hacer copia de seguridad de la base de datos

```bash
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres zeus > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restaurar base de datos desde copia de seguridad

```bash
cat backup_file.sql | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres zeus
```

## Monitoreo

La aplicación incluye los siguientes endpoints de monitoreo:

- `https://tu-dominio.com/api/health` - Estado de salud de la API
- `https://tu-dominio.com/metrics` - Métricas de Prometheus (si está habilitado)

## Solución de Problemas

### Verificar contenedores en ejecución

```bash
docker-compose -f docker-compose.prod.yml ps
```

### Ver logs de un servicio específico

```bash
docker-compose -f docker-compose.prod.yml logs -f nombre_del_servicio
```

### Acceder a la base de datos

```bash
docker-compose -f docker-compose.prod.yml exec db psql -U postgres
```
## Configuración del Frontend

1. **Construir el frontend para producción**
   ```bash
   cd frontend
   npm run build
   ```

2. **Copiar los archivos construidos**
   Asegúrate de que los archivos generados en `frontend/dist` estén disponibles en el directorio `/var/www/frontend` en el servidor.

## Configuración de Dominio y DNS

Asegúrate de que tu dominio esté correctamente configurado:

1. Configura los registros DNS de tu dominio para que apunten a la IP de tu servidor.
2. Configura el dominio en el archivo `nginx/conf.d/zeus.conf`.
3. Asegúrate de que los certificados SSL estén configurados correctamente.

## Seguridad Adicional

1. **Firewall**: Configura un firewall para permitir solo los puertos necesarios (80, 443, 22).
2. **Actualizaciones**: Mantén el sistema operativo y el software actualizados.
3. **Copias de seguridad**: Configura copias de seguridad automáticas de la base de datos.
4. **Monitoreo**: Configura alertas para monitorear el estado del servidor y la aplicación.

## Soporte

Para soporte, por favor abre un issue en el repositorio o contacta al equipo de desarrollo.
