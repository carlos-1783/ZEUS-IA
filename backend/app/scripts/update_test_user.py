import sys
import os
from pathlib import Path

# Añadir el directorio raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash, verify_password

# Datos del usuario de prueba
email = "test@zeus.com"
password = "test123"

# Iniciar sesión de base de datos
session = SessionLocal()

# Buscar el usuario
user = session.query(User).filter(User.email == email).first()

if user:
    print(f"Usuario encontrado: {user.email}")
    print(f"Nombre: {user.full_name}")
    print(f"Activo: {user.is_active}")
    
    # Actualizar la contraseña
    user.hashed_password = get_password_hash(password)
    session.commit()
    
    # Verificar que la contraseña se actualizó correctamente
    if verify_password(password, user.hashed_password):
        print("✅ Contraseña actualizada correctamente")
        print(f"Email: {email}")
        print(f"Password: {password}")
    else:
        print("❌ Error al actualizar la contraseña")
else:
    print(f"❌ Usuario {email} no encontrado")

session.close()
