#!/bin/bash
set -e

echo "=== ZEUS-IA Backend Debug Starting ==="
echo "Current user: $(whoami)"
echo "Working directory: $(pwd)"
echo "Python path: $(which python)"
echo "Python version: $(python --version)"

echo ""
echo "Files in /app:"
ls -la /app/ | head -10

echo ""
echo "Files in current directory:"
ls -la | head -10

echo ""
echo "Environment variables:"
env | grep -E "(PORT|DATABASE|SECRET|ENVIRONMENT)" | head -10

echo ""
echo "Testing Python import..."
python -c "import sys; print('Python sys.path:', sys.path[:3])"

echo ""
echo "Testing FastAPI import..."
python -c "from fastapi import FastAPI; print('FastAPI imported successfully')"

echo ""
echo "Testing app import..."
python -c "from app.main import app; print('App imported successfully')"

echo ""
echo "Starting Uvicorn with debug..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level trace
