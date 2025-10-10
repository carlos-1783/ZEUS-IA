#!/usr/bin/env python3
"""
Script para descargar y optimizar los recursos estáticos de Swagger UI.
Incluye compresión de CSS/JS y generación de hashes de integridad.
"""

import os
import json
import hashlib
import base64
import gzip
import shutil
import requests
from pathlib import Path
from urllib.parse import urljoin

# Configuración
VERSION = "5.9.0"  # Versión de Swagger UI
CDN_URL = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{VERSION}/"
STATIC_DIR = Path(__file__).parent.parent / "app" / "static"
ASSETS = [
    "swagger-ui-bundle.js",
    "swagger-ui-standalone-preset.js",
    "swagger-ui.css",
    "swagger-ui-bundle.js.map",
    "swagger-ui-standalone-preset.js.map",
    "swagger-ui.css.map",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "favicon.ico"
]

def calculate_integrity(content: bytes) -> str:
    """Calcular el hash de integridad para SRI."""
    hash_obj = hashlib.sha384(content)
    return f"sha384-{base64.b64encode(hash_obj.digest()).decode('utf-8')}"

def download_assets():
    """Descargar los recursos de Swagger UI desde el CDN."""
    print("Descargando recursos de Swagger UI...")
    
    # Asegurar que el directorio de destino existe
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    
    integrity_manifest = {}
    
    for asset in ASSETS:
        url = urljoin(CDN_URL, asset)
        print(f"  - Descargando {asset}...")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            content = response.content
            
            # Guardar el archivo original
            output_path = STATIC_DIR / asset
            with open(output_path, 'wb') as f:
                f.write(content)
            
            # Calcular hash de integridad
            integrity = calculate_integrity(content)
            integrity_manifest[asset] = {
                "url": f"/static/{asset}",
                "integrity": integrity
            }
            
            # Comprimir archivos (solo CSS/JS)
            if asset.endswith(('.js', '.css')):
                gz_path = f"{output_path}.gz"
                with gzip.open(gz_path, 'wb', compresslevel=9) as f_out:
                    f_out.write(content)
                print(f"    - Comprimido: {os.path.getsize(output_path):,} → {os.path.getsize(gz_path):,} bytes")
            
            print(f"    - Descargado: {len(content):,} bytes | SRI: {integrity}")
            
        except Exception as e:
            print(f"    Error al descargar {asset}: {e}")
    
    # Guardar el manifiesto de integridad
    with open(STATIC_DIR / "swagger-integrity.json", 'w') as f:
        json.dump(integrity_manifest, f, indent=2)
    
    print("\n¡Descarga completada!")
    print(f"Recursos guardados en: {STATIC_DIR}")

def main():
    """Función principal."""
    print(f"=== Optimizador de Recursos Swagger UI v{VERSION} ===\n")
    
    try:
        download_assets()
        print("\nProceso completado exitosamente.")
    except KeyboardInterrupt:
        print("\nProceso cancelado por el usuario.")
    except Exception as e:
        print(f"\nError inesperado: {e}")
        raise

if __name__ == "__main__":
    main()
