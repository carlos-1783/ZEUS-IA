import sys
import os
from pathlib import Path

# Configurar la codificación de salida a UTF-8
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Añadir el directorio del proyecto al path
sys.path.append(str(Path(__file__).parent))

# Configurar entorno
os.environ["PYTHONIOENCODING"] = "utf-8"

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def reset_and_register():
    db = SessionLocal()
    
    try:
        # Eliminar todos los usuarios existentes
        db.query(User).delete()
        db.commit()
        
        # Crear un nuevo usuario
        user = User(
            email="marketingdigitalper.seo@gmail.com",
            hashed_password=get_password_hash("Carnay19!"),
            full_name="Carlos Perez Martin",
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        db.commit()
        
        print("[SUCCESS] Usuario registrado exitosamente!")
        print(f"Email: marketingdigitalper.seo@gmail.com")
        print(f"Password: Carnay19!")
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_register()
