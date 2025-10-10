import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.models.user import User

def check_user(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"✅ Usuario encontrado:")
            print(f"   ID: {user.id}")
            print(f"   Email: {user.email}")
            print(f"   Activo: {user.is_active}")
            print(f"   Superusuario: {user.is_superuser}")
        else:
            print(f"❌ No se encontró el usuario con email: {email}")
    except Exception as e:
        print(f"❌ Error al buscar el usuario: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_user("marketingdigital per,seo@gmail.com")
