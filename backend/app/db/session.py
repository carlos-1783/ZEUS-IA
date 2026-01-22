from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from app.db.base import SessionLocal
import logging
import time

logger = logging.getLogger(__name__)

def get_db():
    """Obtener sesión de base de datos con reintentos automáticos"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            db: Session = SessionLocal()
            # Verificar que la conexión funciona con una query simple
            try:
                db.execute("SELECT 1")
            except Exception:
                # Si falla la verificación, cerrar y reintentar
                db.close()
                raise
            try:
                yield db
            finally:
                db.close()
            return  # Éxito, salir
            
        except (OperationalError, DisconnectionError) as e:
            error_msg = str(e).lower()
            if attempt < max_retries - 1 and any(keyword in error_msg for keyword in [
                "connection", "conexión", "timeout", "refused", "reset", "operationalerror"
            ]):
                logger.warning(f"Error de conexión a BD (intento {attempt + 1}/{max_retries}), reintentando...")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                logger.error(f"Error crítico de conexión a BD después de {max_retries} intentos: {e}")
                # Lanzar el error para que FastAPI lo maneje
                raise
        except Exception as e:
            # Otros errores, lanzar directamente
            logger.error(f"Error inesperado en get_db: {e}")
            raise
