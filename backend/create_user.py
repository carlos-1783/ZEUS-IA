import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def create_user(email, password, full_name, is_superuser=False):
    db = SessionLocal()
    try:
        # Check if user already exists
        if db.query(User).filter(User.email == email).first():
            print(f"❌ El usuario con email {email} ya existe")
            return False
            
        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=is_superuser
        )
        db.add(user)
        db.commit()
        print(f"✅ Usuario creado exitosamente:")
        print(f"   Email: {email}")
        print(f"   Nombre: {full_name}")
        print(f"   Superusuario: {'Sí' if is_superuser else 'No'}")
        return True
    except Exception as e:
        print(f"❌ Error al crear el usuario: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    create_user(
        email="marketingdigital per,seo@gmail.com",
        password="Carnay19!",
        full_name="Marketing Digital",
        is_superuser=True
    )
