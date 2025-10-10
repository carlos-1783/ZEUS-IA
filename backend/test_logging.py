import logging
import sys
from pathlib import Path

# Configuración básica de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Crear logger
logger = logging.getLogger('test_logger')

def test_logging():
    print("=== Iniciando prueba de logging ===")
    print("Este es un mensaje de print normal")
    
    # Probar diferentes niveles de log
    logger.debug("Este es un mensaje DEBUG")
    logger.info("Este es un mensaje INFO")
    logger.warning("Este es un mensaje WARNING")
    logger.error("Este es un mensaje ERROR")
    logger.critical("Este es un mensaje CRITICAL")
    
    # Probar excepción
    try:
        1 / 0
    except Exception as e:
        logger.exception("Ocurrió una excepción")
    
    print("=== Prueba de logging completada ===")

if __name__ == "__main__":
    test_logging()
