import sqlite3
import jwt
from datetime import datetime, timedelta
import os
from app.core.config import Settings
settings = Settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

def check_user_email():
    """Verifica el email del usuario en la base de datos"""
    try:
        conn = sqlite3.connect('zeus.db')
        cursor = conn.cursor()
        
        # Obtener todos los usuarios
        cursor.execute("SELECT id, email FROM users")
        users = cursor.fetchall()
        
        print("Usuarios en la base de datos:")
        for user_id, email in users:
            print(f"ID: {user_id}, Email: {email}")
            
            # Verificar si el email contiene comas o espacios
            if ',' in email or ' ' in email:
                print(f"  ⚠️  ADVERTENCIA: El email contiene comas o espacios")
                
                # Sugerir corrección
                new_email = email.replace(' ', '').replace(',', '.')
                print(f"  🔄 Sugerencia de corrección: {new_email}")
                
                # Preguntar si se desea corregir
                confirm = input("¿Desea corregir este email? (s/n): ")
                if confirm.lower() == 's':
                    cursor.execute(
                        "UPDATE users SET email = ? WHERE id = ?",
                        (new_email, user_id)
                    )
                    conn.commit()
                    print("  ✅ Email actualizado correctamente")
                    return new_email
        
        return users[0][1] if users else None
        
    except sqlite3.Error as e:
        print(f"Error al acceder a la base de datos: {e}")
        return None
    finally:
        conn.close()

def generate_jwt_token(email):
    """Genera un nuevo token JWT con el email proporcionado"""
    if not email:
        print("No se pudo obtener el email del usuario")
        return None
    
    try:
        # Configuración del token
        
        # Crear payload del token
        payload = {
            'sub': email,
            'user_id': 1,  # Ajustar según sea necesario
            'type': 'access',
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow()
        }
        
        # Generar token
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        print(f"\n🔑 Nuevo token JWT generado:")
        print(token)
        print("\n⚠️  Copia este token y péguelo en la consola del navegador con el siguiente comando:")
        print(f"localStorage.setItem('access_token', '{token}');")
        
        return token
        
    except Exception as e:
        print(f"Error al generar el token: {e}")
        return None

if __name__ == "__main__":
    print("=== Verificación de Usuario y Generación de Token JWT ===\n")
    
    # 1. Verificar email en la base de datos
    print("🔍 Verificando usuario en la base de datos...")
    email = check_user_email()
    
    if email:
        print(f"\n✅ Email encontrado: {email}")
        
        # 2. Generar nuevo token JWT
        print("\n🔄 Generando nuevo token JWT...")
        token = generate_jwt_token(email)
        
        if token:
            print("\n🎉 ¡Listo! Copia el token generado y péguelo en la consola del navegador.")
        else:
            print("\n❌ No se pudo generar el token. Por favor, verifica los errores.")
    else:
        print("\n❌ No se pudo encontrar el usuario en la base de datos.")
    
    input("\nPresiona Enter para salir...")
