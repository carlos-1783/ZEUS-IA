# ========================================
# ZEUS-IA PRODUCTION DOCKERFILE
# ========================================
# Multi-stage build for Railway deployment

# Stage 1: Build Frontend
FROM mirror.gcr.io/library/node:18-slim AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

# Copy frontend source
COPY frontend/ ./

# Build frontend
RUN npm run build

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
