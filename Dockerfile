# Dockerfile ultra-simple para Railway
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

# Exponer el puerto
EXPOSE 8000
ENV PORT=8000

# Ejecutar diagnóstico y luego iniciar la app
CMD ["python", "-c", "print('=== ZEUS-IA Backend Starting ==='); exec(open('test_imports.py').read()); print('=== Starting Server ==='); from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')"]