import sys
import os
from pathlib import Path

# Añadir el directorio raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

# Datos del usuario de prueba
email = "test@zeus.com"
password = "test123"
full_name = "Usuario de Prueba"

# Iniciar sesión de base de datos
session = SessionLocal()

# Verificar si el usuario ya existe
user = session.query(User).filter(User.email == email).first()
if user:
    print("El usuario de prueba ya existe.")
    print(f"Email: {email}")
    print(f"Password: {password}")
else:
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        is_active=True,
        is_superuser=False
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    print("Usuario de prueba creado correctamente.")
    print(f"Email: {email}")
    print(f"Password: {password}")

session.close()
