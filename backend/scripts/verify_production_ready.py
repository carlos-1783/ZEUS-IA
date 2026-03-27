#!/usr/bin/env python3
"""Verificación rápida: sin secrets hardcodeados en producción."""
import os
import sys

# Subir al backend para importar app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ENV = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "production")).lower()
DEV_SECRET = "dev_default_secret_key_change_in_production"
DEV_REFRESH = "dev_default_refresh_secret"


def main():
    errors = []
    if ENV == "production":
        sk = os.getenv("SECRET_KEY", "")
        if not sk or DEV_SECRET in sk:
            errors.append("SECRET_KEY debe estar definida y no usar valor de desarrollo en producción")
        rk = os.getenv("REFRESH_TOKEN_SECRET", "")
        if not rk or DEV_REFRESH in rk:
            errors.append("REFRESH_TOKEN_SECRET debe estar definida y no usar valor de desarrollo en producción")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("OK: Verificación de secrets superada")


if __name__ == "__main__":
    main()
