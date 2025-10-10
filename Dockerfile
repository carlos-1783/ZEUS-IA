# Dockerfile optimizado para FastAPI en Railway
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

# Comando optimizado para FastAPI con uvicorn
CMD ["python", "-c", "import os; port = int(os.environ.get('PORT', 8000)); print('=== ZEUS-IA FastAPI Backend Starting ==='); print(f'Host: 0.0.0.0, Port: {port}'); from app.main import app; import uvicorn; print('✅ FastAPI app loaded successfully'); print('🚀 Starting Uvicorn server...'); uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')"]