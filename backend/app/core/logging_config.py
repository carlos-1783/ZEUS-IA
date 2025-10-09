"""
Configuración de logging para ZEUS-IA
"""
import logging
import logging.handlers
import os
from datetime import datetime
from app.config import settings

def setup_logging():
    """Configurar sistema de logging"""
    
    # Crear directorio de logs si no existe
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar formato de logs
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Logger principal
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Handler para archivo
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'zeus-ia.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # Logger específico para seguridad
    security_logger = logging.getLogger('security')
    security_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'security.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    security_handler.setFormatter(log_format)
    security_logger.addHandler(security_handler)
    
    # Logger específico para API
    api_logger = logging.getLogger('api')
    api_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'api.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    api_handler.setFormatter(log_format)
    api_logger.addHandler(api_handler)
    
    return logger

def log_security_event(event_type: str, details: dict, user_ip: str = None):
    """Registrar evento de seguridad"""
    security_logger = logging.getLogger('security')
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "details": details,
        "user_ip": user_ip
    }
    security_logger.warning(f"Security Event: {event}")

def log_api_request(method: str, path: str, status_code: int, response_time: float, user_ip: str = None):
    """Registrar request de API"""
    api_logger = logging.getLogger('api')
    api_logger.info(f"API Request: {method} {path} - {status_code} - {response_time}ms - IP: {user_ip}")

# Configurar logging al importar
setup_logging()