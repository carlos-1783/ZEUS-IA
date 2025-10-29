"""
⚡ ZEUS-IA - Setup y Test ⚡
Script para configurar y probar el sistema
"""

import os
import sys
from pathlib import Path

# Cargar .env si existe
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)
    print("✅ Variables de entorno cargadas desde .env")

# Verificar que la API key esté configurada
if not os.getenv("OPENAI_API_KEY"):
    print("❌ ERROR: OPENAI_API_KEY no configurada")
    print("\n📋 Configura tu API key de una de estas formas:")
    print("   1. Variable de entorno: export OPENAI_API_KEY='tu-api-key'")
    print("   2. Archivo .env en la raíz del proyecto")
    print("   3. Railway: Settings > Variables > OPENAI_API_KEY")
    sys.exit(1)

# Importar y ejecutar tests
from test_agents import main

if __name__ == "__main__":
    print("🔑 API Key configurada")
    print("🚀 Iniciando tests del sistema ZEUS...\n")
    main()

