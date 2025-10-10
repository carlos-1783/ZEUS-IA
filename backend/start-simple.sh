#!/bin/bash
set -e

echo "=== ZEUS-IA Backend Starting ==="
echo "Working directory: $(pwd)"
echo "Files present:"
ls -la | head -20

echo ""
echo "Environment variables:"
echo "PORT: ${PORT:-8000}"
echo "ENVIRONMENT: ${ENVIRONMENT:-not set}"
echo "DATABASE_URL: ${DATABASE_URL:0:30}..."

echo ""
echo "Python version:"
python --version

echo ""
echo "Starting Uvicorn server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level debug
