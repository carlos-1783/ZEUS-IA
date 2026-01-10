"""
Script para verificar credenciales de Google Ads configuradas
Verifica que credenciales estan configuradas y cuales faltan
"""
import os
import sys
from dotenv import load_dotenv

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Cargar variables de entorno
load_dotenv()

def check_google_ads_credentials():
    """Verificar estado de credenciales de Google Ads"""
    
    print("=" * 80)
    print("VERIFICACION DE CREDENCIALES DE GOOGLE ADS")
    print("=" * 80)
    print()
    
    # Credenciales necesarias
    credentials = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": {
            "required": True,
            "description": "Token de desarrollador de Google Ads API",
            "where": "https://ads.google.com/aw/apicenter"
        },
        "GOOGLE_ADS_CLIENT_ID": {
            "required": True,
            "description": "Client ID de OAuth2 desde Google Cloud Console",
            "where": "https://console.cloud.google.com/apis/credentials"
        },
        "GOOGLE_ADS_CLIENT_SECRET": {
            "required": True,
            "description": "Client Secret de OAuth2 desde Google Cloud Console",
            "where": "https://console.cloud.google.com/apis/credentials"
        },
        "GOOGLE_ADS_REFRESH_TOKEN": {
            "required": False,
            "description": "Refresh Token de OAuth2 (opcional pero recomendado)",
            "where": "Generado mediante OAuth2 flow"
        },
        "GOOGLE_ADS_CUSTOMER_ID": {
            "required": True,
            "description": "ID de cuenta de Google Ads (129-046-8001)",
            "where": "Tu cuenta de Google Ads"
        },
        "GOOGLE_ADS_MODE": {
            "required": False,
            "description": "Modo de operación (SANDBOX o PRODUCTION)",
            "where": "Configuración interna"
        }
    }
    
    configured = []
    missing = []
    
    for env_var, info in credentials.items():
        value = os.getenv(env_var, "")
        
        # Verificar si está configurado
        if value and value.lower() not in ["pendiente", "pending", "", "your_token_here", "your_client_id_here"]:
            configured.append({
                "variable": env_var,
                "status": "[OK] CONFIGURADO",
                "value_preview": f"{value[:20]}..." if len(value) > 20 else value,
                "required": info["required"]
            })
        else:
            missing.append({
                "variable": env_var,
                "status": "[FALTA] FALTANTE" if info["required"] else "[OPCIONAL]",
                "description": info["description"],
                "where": info["where"],
                "required": info["required"]
            })
    
    # Mostrar resultados
    print("CREDENCIALES CONFIGURADAS:")
    print("-" * 80)
    if configured:
        for cred in configured:
            required_label = " (OBLIGATORIO)" if cred["required"] else " (OPCIONAL)"
            print(f"{cred['status']} {cred['variable']}{required_label}")
            print(f"   Vista previa: {cred['value_preview']}")
            print()
    else:
        print("   No se encontraron credenciales configuradas")
        print()
    
    print("CREDENCIALES FALTANTES:")
    print("-" * 80)
    if missing:
        for cred in missing:
            print(f"{cred['status']} {cred['variable']}")
            print(f"   Descripción: {cred['description']}")
            print(f"   Dónde obtener: {cred['where']}")
            print()
    else:
        print("   ✅ Todas las credenciales están configuradas")
        print()
    
    # Resumen
    print("=" * 80)
    print("RESUMEN:")
    print("-" * 80)
    print(f"[OK] Configuradas: {len(configured)}")
    print(f"[FALTA] Faltantes (obligatorias): {sum(1 for c in missing if c['required'])}")
    print(f"[OPCIONAL] Opcionales faltantes: {sum(1 for c in missing if not c['required'])}")
    print()
    
    # Verificar si PERSEO puede funcionar
    required_missing = [c for c in missing if c["required"]]
    if required_missing:
        print("ADVERTENCIA: PERSEO NO PODRA FUNCIONAR COMPLETAMENTE")
        print(f"   Faltan {len(required_missing)} credenciales obligatorias:")
        for cred in required_missing:
            print(f"   - {cred['variable']}")
        print()
        print("ACCION NECESARIA:")
        print("   1. Obten las credenciales faltantes siguiendo la guia:")
        print("      docs/GUIA_CONFIGURACION_GOOGLE_ADS_PASO_A_PASO.md")
        print("   2. Anadelas en Railway como variables de entorno")
        print("   3. Reinicia el servicio backend")
    else:
        print("[OK] PERSEO PUEDE FUNCIONAR")
        print("   Todas las credenciales obligatorias estan configuradas")
    
    print("=" * 80)
    
    return {
        "configured": configured,
        "missing": missing,
        "can_work": len(required_missing) == 0
    }

if __name__ == "__main__":
    check_google_ads_credentials()

