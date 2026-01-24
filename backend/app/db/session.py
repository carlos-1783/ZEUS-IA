from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from fastapi import HTTPException
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
            try:
                from sqlalchemy import text
                db.execute(text("SELECT 1"))
            except Exception as verify_error:
                db.close()
                error_msg = str(verify_error).lower()
                if any(k in error_msg for k in ["connection", "conexión", "timeout"]):
                    raise
                raise
            try:
                yield db
            finally:
                db.close()
            return

        except (OperationalError, DisconnectionError) as e:
            error_msg = str(e).lower()
            if attempt < max_retries - 1 and any(
                k in error_msg for k in [
                    "connection", "conexión", "timeout", "refused", "reset", "operationalerror"
                ]
            ):
                logger.warning(
                    "Error de conexión a BD (intento %d/%d), reintentando...",
                    attempt + 1, max_retries,
                )
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            logger.error("Error crítico de conexión a BD después de %d intentos: %s", max_retries, e)
            raise
        except HTTPException:
            # 401 Token expirado, 403, etc.: no son errores de BD, propagar sin logear como get_db
            raise
        except Exception as e:
            logger.error("Error inesperado en get_db: %s", e)
            raise
