from pydantic import PostgresDsn
from pydantic_settings import BaseSettings
from typing import Optional, List, Dict, Any

class Settings(BaseSettings):
    # Application settings
    PROJECT_NAME: str = "ZEUS-IA"
    VERSION: str = "1.0.0"  # Versión de la aplicación
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"  # Prefijo para las rutas de la API
    
    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Security
    SECRET_KEY: str = "6895b411b45b5946b46bf7970f4d7e17aa69dfc5da4696cb15686625e5eccf2b"
    ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "zeus-ia-backend"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 11520  # 8 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    
    # CORS Configuration - Permitir conexiones desde los puertos comunes del frontend
    BACKEND_CORS_ORIGINS: list[str] = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000").split(",")
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./zeus.db"  # Default SQLite for development
    
    # CORS Headers Configuration
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    CORS_EXPOSE_HEADERS: list[str] = ["Content-Disposition"]
    
    # Static Files Configuration
    STATIC_URL: str = "/static"
    STATIC_DIR: str = "static"  # Directorio relativo a la raíz del proyecto
    
    # Ensure SECRET_KEY is in the correct format for JWT
    @property
    def SECRET_KEY_BYTES(self) -> bytes:
        """
        Returns the secret key in bytes format for JWT operations.
        This ensures consistent key format across the application.
        """
        if hasattr(self, '_secret_key_bytes'):
            return self._secret_key_bytes
            
        secret_key = self.SECRET_KEY
        
        # Log the type and first few characters of the key for debugging
        print("\n[CONFIG] ===== MANEJO DE CLAVE SECRETA JWT =====")
        print(f"[CONFIG] Tipo de clave original: {type(secret_key).__name__}")
        print(f"[CONFIG] Valor de la clave (inicio): {str(secret_key)[:10]}...")
        
        # Forzar la conversión a string y luego a bytes de forma consistente
        try:
            # 1. Convertir a string si no lo es
            if not isinstance(secret_key, str):
                secret_key = str(secret_key)
                print("[CONFIG] Convertida a string")
            
            # 2. Verificar si es una cadena hexadecimal válida
            if len(secret_key) == 64 and all(c in '0123456789abcdef' for c in secret_key.lower()):
                print("[CONFIG] Detectada clave en formato hexadecimal")
                self._secret_key_bytes = bytes.fromhex(secret_key)
            else:
                print("[CONFIG] Usando clave como string UTF-8")
                self._secret_key_bytes = secret_key.encode('utf-8')
            
            # 3. Asegurar que la longitud sea adecuada para el algoritmo HS256
            min_key_length = 32  # 256 bits para HS256
            if len(self._secret_key_bytes) < min_key_length:
                print(f"[CONFIG] ADVERTENCIA: La clave es demasiado corta ({len(self._secret_key_bytes)} bytes). Se recomiendan al menos {min_key_length} bytes para HS256")
                # Rellenar con ceros si es necesario (aunque no es lo ideal)
                self._secret_key_bytes = self._secret_key_bytes.ljust(min_key_length, b'\0')
            
            print(f"[CONFIG] Clave final (tipo): {type(self._secret_key_bytes).__name__}")
            print(f"[CONFIG] Longitud de la clave: {len(self._secret_key_bytes)} bytes")
            print(f"[CONFIG] Prefijo de la clave (hex): {self._secret_key_bytes[:16].hex()}...")
            print("[CONFIG] =======================================\n")
            
            return self._secret_key_bytes
            
        except Exception as e:
            print(f"[CONFIG] ERROR al procesar la clave secreta: {str(e)}")
            raise ValueError("Error en el formato de la clave secreta JWT") from e

# Crear una instancia global de Settings que será importada por otros módulos
settings = Settings()

# Mensaje de confirmación al cargar la configuración
print("\n[CONFIG] Configuración cargada correctamente")
print(f"[CONFIG] Entorno: {settings.ENVIRONMENT}")
print(f"[CONFIG] Debug: {'Activado' if settings.DEBUG else 'Desactivado'}")
print(f"[CONFIG] Servidor: {settings.HOST}:{settings.PORT}")
print(f"[CONFIG] Algoritmo JWT: {settings.ALGORITHM}")
print("[CONFIG] =======================================\n")