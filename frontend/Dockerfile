# ===============================================
# ZEUS-IA Frontend - Dockerfile para Producción
# ===============================================

# Etapa de construcción
FROM node:18-alpine AS builder

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apk add --no-cache git

# Copiar archivos de configuración primero para aprovechar la caché de Docker
COPY package*.json ./
COPY vite.config.ts ./
COPY tsconfig.json ./
COPY tsconfig.node.json ./

# Instalar dependencias
RUN npm ci --only=production --silent

# Copiar el resto de los archivos de la aplicación
COPY . .

# Construir la aplicación para producción
RUN npm run build

# Etapa de producción
FROM nginx:alpine

# Crear usuario no-root para seguridad
RUN addgroup -g 1001 -S zeus && \
    adduser -S zeus -u 1001

# Instalar curl para health checks
RUN apk add --no-cache curl

# Copiar configuración personalizada de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar los archivos construidos desde la etapa de construcción
COPY --from=builder /app/dist /usr/share/nginx/html

# Configurar permisos
RUN chown -R zeus:zeus /usr/share/nginx/html && \
    chown -R zeus:zeus /var/cache/nginx && \
    chown -R zeus:zeus /var/log/nginx && \
    chown -R zeus:zeus /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R zeus:zeus /var/run/nginx.pid

# Cambiar al usuario no-root
USER zeus

# Exponer el puerto 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Iniciar Nginx
CMD ["nginx", "-g", "daemon off;"]