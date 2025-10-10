# Dockerfile optimizado para Railway
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY ./backend/requirements.txt ./requirements.txt

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY ./backend/ .

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/static

# Exponer el puerto (Railway usa $PORT dinámicamente)
EXPOSE 8000
ENV PORT=8000

# Comando directo que usa el puerto de Railway
CMD ["python", "-c", "import os; port = int(os.environ.get('PORT', 8000)); print(f'Starting ZEUS-IA on port {port}'); from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')"]