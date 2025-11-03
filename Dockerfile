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

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies (limpiar cache primero)
RUN npm cache clean --force || true
RUN npm install --legacy-peer-deps --no-optional

# Copy frontend source
COPY frontend/ ./

# FORZAR REBUILD LIMPIO - eliminar todo caché
RUN rm -rf dist/ node_modules/.vite .vite/ .cache/ || true

# Build frontend con forzado
ENV NODE_ENV=production
ENV VITE_FORCE_BUILD=true
RUN npm run build -- --force

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

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./static

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
