#!/bin/bash
# ========================================
# RAILWAY BUILD SCRIPT
# ========================================

echo "🚀 Building ZEUS-IA for Railway..."

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm ci --legacy-peer-deps

# Build frontend
echo "🔨 Building frontend..."
npm run build

# Copy frontend to backend static
echo "📁 Copying frontend to backend..."
cp -r dist ../backend/static

# Go back to root
cd ..

# Install backend dependencies
echo "🐍 Installing backend dependencies..."
cd backend
pip install -r requirements.txt

echo "✅ Build completed successfully!"
echo "🚀 Ready for Railway deployment!"
