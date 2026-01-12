#!/usr/bin/env python3
"""
Script para generar claves secretas seguras para Railway
"""
import secrets
import sys

# Configurar stdout para UTF-8 (Windows)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("🔐 GENERADOR DE CLAVES SECRETAS PARA ZEUS-IA")
print("=" * 80)
print()

# Generar SECRET_KEY (64 caracteres hex = 256 bits)
secret_key = secrets.token_hex(32)
print("1️⃣  SECRET_KEY (para JWT y encriptación)")
print("   " + "=" * 76)
print(f"   {secret_key}")
print()
print("   📋 Copia este valor y pégalo en Railway como SECRET_KEY")
print()

# Generar REFRESH_TOKEN_SECRET
refresh_secret = secrets.token_hex(32)
print("2️⃣  REFRESH_TOKEN_SECRET (para refresh tokens)")
print("   " + "=" * 76)
print(f"   {refresh_secret}")
print()
print("   📋 Copia este valor y pégalo en Railway como REFRESH_TOKEN_SECRET")
print()

# Generar una contraseña segura para el superusuario
import string
password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
superuser_password = ''.join(secrets.choice(password_chars) for _ in range(16))
print("3️⃣  FIRST_SUPERUSER_PASSWORD (contraseña para el superusuario)")
print("   " + "=" * 76)
print(f"   {superuser_password}")
print()
print("   📋 Copia este valor y pégalo en Railway como FIRST_SUPERUSER_PASSWORD")
print("   ⚠️  IMPORTANTE: Guarda esta contraseña de forma segura")
print()

print("=" * 80)
print("✅ CLAVES GENERADAS EXITOSAMENTE")
print("=" * 80)
print()
print("📝 SIGUIENTES PASOS:")
print("   1. Copia cada valor y pégalo en Railway Variables")
print("   2. Reinicia el servicio en Railway")
print("   3. Verifica que el login funcione correctamente")
print()
