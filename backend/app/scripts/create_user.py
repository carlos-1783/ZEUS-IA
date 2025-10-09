import sys
import os
from pathlib import Path

# Añadir el directorio raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

# Datos del usuario
email = "marketingdigitalper.seo@gmail.com"
password = "Carnay19"
full_name = "Marketing Digital"

# Iniciar sesión de base de datos
session = SessionLocal()

# Verificar si el usuario ya existe
user = session.query(User).filter(User.email == email).first()
if user:
    print("El usuario ya existe.")
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
    print("Usuario creado correctamente.")

session.close() 