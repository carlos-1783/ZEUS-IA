# ========================================
# ZEUS-IA PRODUCTION DOCKERFILE v1.0.6
# ========================================
# Multi-stage build for Railway deployment
# REBUILD: 2025-11-03 - GLB Avatars Fix

# Stage 1: Build Frontend
FROM mirror.gcr.io/library/node:18-slim AS frontend-builder

# Install build dependencies for lightningcss
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/frontend

# Lockfile + manifest (npm ci = build reproducible en Railway)
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies (limpiar cache primero)
RUN npm cache clean --force || true
RUN npm ci --legacy-peer-deps --no-audit --fund=false || (echo "npm ci falló; intentando npm install" && npm install --legacy-peer-deps --no-optional)

# Copy frontend source
COPY frontend/ ./

# FORZAR REBUILD LIMPIO - eliminar todo caché
RUN rm -rf dist/ node_modules/.vite .vite/ .cache/ || true

# API: vacío = en runtime el SPA usa el mismo origen + /api/v1 (un solo servicio). Para API en otro host: --build-arg VITE_API_BASE_URL=https://api.ejemplo.com/api/v1
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG REACT_APP_API_URL=
ENV REACT_APP_API_URL=${REACT_APP_API_URL}
# Build frontend con forzado (Vite → carpeta dist/)
ENV NODE_ENV=production
ENV VITE_FORCE_BUILD=true
RUN npm run build -- --force

# Fallar el build de imagen si no hay SPA (evita desplegar backend “ciego”)
RUN test -f dist/index.html && test -s dist/index.html \
    && test -d dist/assets \
    && echo "OK: Vite dist/index.html + dist/assets presentes"

# Debug: Show build output
RUN echo "=== BUILD OUTPUT ===" && ls -la dist/
RUN echo "=== DIST CONTENTS ===" && find dist/ -type f -name "*.js" | head -5
RUN echo "=== INDEX.HTML ===" && cat dist/index.html | head -10

# Stage 2: Backend with Frontend
FROM mirror.gcr.io/library/python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000
# 1 worker: evita duplicar memoria (OpenAI + agentes + FastAPI) → OOM/SIGKILL en Railway pequeño.
ENV WEB_CONCURRENCY=1
ENV GUNICORN_TIMEOUT=300
ENV GUNICORN_GRACEFUL_TIMEOUT=300
# Menos fragmentación heap glibc en procesos multihilo (Python + executor).
ENV MALLOC_ARENA_MAX=2
ENV GUNICORN_WORKER_TMPDIR=/tmp
# Vídeo de presentación PERSEO (slides + copy). Si Railway marca OOM, poner PERSEO_CHAT_AUTO_VIDEO=false en Variables.
ENV PERSEO_CHAT_AUTO_VIDEO=true
# Encode más ligero que el default del código (1920 + preset slow).
ENV PERSEO_VIDEO_WIDTH=1280
ENV PERSEO_VIDEO_SECONDS_PER_SLIDE=3
ENV PERSEO_FFMPEG_PRESET=veryfast
ENV PERSEO_VIDEO_CROSSFADE_SEC=0.2
ENV PERSEO_VIDEO_JOB_TIMEOUT_SEC=300

# Install system dependencies (ffmpeg: MoviePy/libx264 más fiable en contenedor slim)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Set work directory (debe coincidir con resolución de STATIC_DIR en app/core/config.py)
WORKDIR /app
ENV ZEUS_APP_ROOT=/app

# Copy backend requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# LIMPIAR TODO EL CACHÉ DE PYTHON (forzar recarga de módulos)
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find . -type f -name "*.pyc" -delete 2>/dev/null || true
RUN find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Copy built frontend from stage 1 (Vite outDir = dist → backend static/)
COPY --from=frontend-builder /app/frontend/dist ./static

# Imagen inválida si el SPA no quedó copiado
RUN test -f static/index.html && test -s static/index.html \
    && echo "OK: static/index.html presente para FastAPI"

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check (sin dependencia de curl y usando PORT dinámico)
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=5 \
    CMD python -c "import os,urllib.request; p=os.getenv('PORT','8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/v1/health', timeout=5)"

# Gunicorn + UvicornWorker. WEB_CONCURRENCY=2 solo si el plan Railway tiene RAM suficiente (p. ej. ≥1 GB).
CMD ["sh", "-c", "gunicorn -c gunicorn.conf.py app.main:app"]
