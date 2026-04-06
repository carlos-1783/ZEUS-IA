"""
Crea un usuario en la base de datos configurada por DATABASE_URL (local o Railway)
si el email aún no existe. Útil para alinear usuarios de producción con SQLite local.

Uso (desde la carpeta backend, con el venv activado):
  python scripts/dev_add_user.py correo@ejemplo.com "Password1a" --full-name "Nombre" --phone 600123456

La contraseña debe cumplir las mismas reglas que el registro (≥8, mayúscula, minúscula, número).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def _password_ok(p: str) -> tuple[bool, str]:
    if len(p) < 8:
        return False, "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", p):
        return False, "Necesita una mayúscula"
    if not re.search(r"[a-z]", p):
        return False, "Necesita una minúscula"
    if not re.search(r"[0-9]", p):
        return False, "Necesita un número"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Añadir usuario a la BD actual (desarrollo)")
    parser.add_argument("email", help="Email (se normaliza a minúsculas)")
    parser.add_argument("password", help="Contraseña fuerte")
    parser.add_argument("--full-name", default="Usuario local", dest="full_name")
    parser.add_argument("--phone", default="600000000")
    parser.add_argument("--superuser", action="store_true", help="Marcar como superusuario")
    args = parser.parse_args()

    ok, msg = _password_ok(args.password)
    if not ok:
        print(f"Contraseña inválida: {msg}")
        return 1

    email = args.email.strip().lower()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"Ya existe el usuario: {email} (id={existing.id})")
            return 0

        u = User(
            email=email,
            full_name=(args.full_name or "Usuario").strip()[:200],
            phone=(args.phone or "").strip()[:32] or None,
            hashed_password=get_password_hash(args.password),
            is_active=True,
            is_superuser=args.superuser,
            role="owner",
        )
        db.add(u)
        db.commit()
        db.refresh(u)

        try:
            from services.global_company_bootstrap import ensure_user_company_link_for_operations

            ensure_user_company_link_for_operations(db, u)
        except Exception as e:
            print(f"Aviso: no se pudo enlazar empresa por defecto: {e}")

        print(f"OK creado user_id={u.id} email={email} superuser={args.superuser}")
        return 0
    except IntegrityError:
        db.rollback()
        print(f"Error integridad (email duplicado): {email}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
