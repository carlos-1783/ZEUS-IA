#!/usr/bin/env python3
"""
Script para verificar el estado de usuarios en Railway
"""

import requests
import json

def verificar_backend_railway():
    """Verificar si el backend de Railway está funcionando"""
    
    base_url = "https://zeus-ia-production-16d8.up.railway.app"
    
    print("🔍 Verificando estado del backend de Railway...")
    print(f"URL: {base_url}")
    
    try:
        # Verificar health check
        health_response = requests.get(f"{base_url}/health", timeout=10)
        print(f"✅ Health Check: {health_response.status_code}")
        if health_response.status_code == 200:
            print(f"   Response: {health_response.json()}")
        
        # Verificar endpoint de debug
        debug_response = requests.get(f"{base_url}/debug", timeout=10)
        print(f"✅ Debug Endpoint: {debug_response.status_code}")
        if debug_response.status_code == 200:
            print(f"   Response: {debug_response.text[:200]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error conectando al backend: {e}")
        return False
    
    return True

def probar_login():
    """Probar login con las credenciales correctas"""
    
    base_url = "https://zeus-ia-production-16d8.up.railway.app"
    login_url = f"{base_url}/api/v1/auth/login"
    
    print("\n🔐 Probando login con credenciales...")
    
    # Credenciales correctas según el backend
    credentials = {
        "username": "marketingdigitalper.seo@gmail.com",
        "password": "Carnay19",
        "grant_type": "password"
    }
    
    try:
        response = requests.post(
            login_url,
            data=credentials,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            timeout=15
        )
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ LOGIN EXITOSO!")
            data = response.json()
            print(f"   Access Token: {data.get('access_token', 'N/A')[:50]}...")
            print(f"   Token Type: {data.get('token_type', 'N/A')}")
            print(f"   Expires In: {data.get('expires_in', 'N/A')}")
            return True
        else:
            print("❌ LOGIN FALLÓ")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error en login: {e}")
        return False

if __name__ == "__main__":
    print("🚀 VERIFICACIÓN DE RAILWAY BACKEND")
    print("=" * 50)
    
    # Verificar backend
    if verificar_backend_railway():
        print("\n✅ Backend está funcionando")
        
        # Probar login
        if probar_login():
            print("\n🎉 ¡TODO FUNCIONA CORRECTAMENTE!")
            print("Las credenciales son:")
            print("📧 Email: marketingdigitalper.seo@gmail.com")
            print("🔐 Contraseña: Carnay19")
        else:
            print("\n❌ El login falló")
            print("Posibles causas:")
            print("1. El usuario no se creó correctamente")
            print("2. La base de datos no está configurada")
            print("3. Hay un problema con la autenticación")
    else:
        print("\n❌ El backend no está funcionando")
        print("Verifica que Railway esté desplegado correctamente")
    
    print("\n" + "=" * 50)
