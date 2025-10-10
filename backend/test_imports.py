#!/usr/bin/env python3
"""
Script de diagnóstico para ZEUS-IA Backend
Prueba todos los imports críticos antes del despliegue
"""

import sys
import os
import traceback

def test_import(module_name, description):
    """Prueba un import específico y muestra el resultado"""
    try:
        exec(f"import {module_name}")
        print(f"✅ {description}: {module_name}")
        return True
    except Exception as e:
        print(f"❌ {description}: {module_name}")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False

def main():
    print("=== ZEUS-IA Backend - Diagnóstico de Imports ===")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python path: {sys.path[:3]}")
    print()
    
    # Pruebas básicas
    tests = [
        ("os", "Sistema operativo"),
        ("json", "JSON"),
        ("logging", "Logging"),
        ("typing", "Typing"),
        ("contextlib", "Contextlib"),
    ]
    
    print("📦 Pruebas de módulos básicos:")
    for module, desc in tests:
        test_import(module, desc)
    
    print()
    print("🔧 Pruebas de FastAPI:")
    fastapi_tests = [
        ("fastapi", "FastAPI"),
        ("fastapi.responses", "FastAPI Responses"),
        ("fastapi.middleware.cors", "CORS Middleware"),
        ("fastapi.staticfiles", "Static Files"),
        ("uvicorn", "Uvicorn"),
        ("sqlalchemy.orm", "SQLAlchemy ORM"),
    ]
    
    for module, desc in fastapi_tests:
        test_import(module, desc)
    
    print()
    print("🏗️ Pruebas de la aplicación:")
    app_tests = [
        ("app.core.config", "Config"),
        ("app.core.logging_config", "Logging Config"),
        ("app.core.middlewares", "Middlewares"),
        ("app.core.routes", "Routes"),
        ("app.core.docs", "Docs"),
        ("app.main", "Main App"),
    ]
    
    all_passed = True
    for module, desc in app_tests:
        if not test_import(module, desc):
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 ¡TODOS LOS IMPORTS PASARON!")
        print("✅ La aplicación debería funcionar correctamente")
        
        # Probar crear la instancia de la app
        try:
            from app.main import app
            print("✅ Instancia de FastAPI creada exitosamente")
            print(f"   App title: {app.title}")
            print(f"   App version: {app.version}")
        except Exception as e:
            print(f"❌ Error creando instancia de FastAPI: {e}")
            all_passed = False
    else:
        print("💥 ALGUNOS IMPORTS FALLARON")
        print("❌ La aplicación NO funcionará correctamente")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
