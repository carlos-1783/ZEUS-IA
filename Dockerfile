# ===============================================
# ZEUS-IA Backend - Dockerfile para Railway
# ===============================================

FROM python:3.11-slim AS production

# Crear usuario no-root para seguridad
RUN groupadd -r zeus && useradd -r -g zeus zeus

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requisitos desde backend/
COPY ./backend/requirements.txt ./requirements.txt

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación desde backend/
COPY ./backend/ .

# Copiar script de inicio
COPY backend/start.sh /app/start.sh

# Crear directorios necesarios y dar permisos
RUN mkdir -p /app/logs /app/static && \
    chmod +x /app/start.sh && \
    chown -R zeus:zeus /app

# Cambiar al usuario no-root
USER zeus

# Exponer el puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando para ejecutar con el script de inicio
CMD ["/app/start.sh"]
