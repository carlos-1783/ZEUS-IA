import sys
from pathlib import Path
import argparse

# Añadir el directorio raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.db.session import SessionLocal
from app.models.user import User

session = SessionLocal()

parser = argparse.ArgumentParser(description="Listar y/o eliminar usuarios por email.")
parser.add_argument('--delete', type=str, help='Email del usuario a eliminar')
args = parser.parse_args()

if args.delete:
    user_to_delete = session.query(User).filter(User.email == args.delete).first()
    if user_to_delete:
        session.delete(user_to_delete)
        session.commit()
        print(f"Usuario '{args.delete}' borrado.")
    else:
        print(f"No se encontró el usuario '{args.delete}'.")

users = session.query(User).all()

if not users:
    print("No hay usuarios en la base de datos.")
else:
    for user in users:
        print(f"Email: {user.email}, Nombre: {user.full_name}, Activo: {user.is_active}, Superuser: {user.is_superuser}")

session.close() 