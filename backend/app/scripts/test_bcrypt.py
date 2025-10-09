import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from passlib.context import CryptContext
from backend.app.db.base import get_db
from backend.app.models.user import User

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password = "Carnay19!"
    hashed = pwd_context.hash(password)
    print("Hash generado:", hashed)
    print("Verificación correcta:", pwd_context.verify(password, hashed))
    print("Verificación incorrecta:", pwd_context.verify("otraClave", hashed))

    # Obtener el hash real de la base de datos
    db = next(get_db())
    user = db.query(User).filter(User.email == "marketingdigitalper.seo@gmail.com").first()
    if user:
        print("Hash en base de datos:", user.hashed_password)
        print("Verificación contra hash de BD:", pwd_context.verify(password, user.hashed_password))
    else:
        print("Usuario no encontrado en la base de datos")
except Exception as e:
    import traceback
    print("ERROR DETECTADO:\n", traceback.format_exc())

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password) 