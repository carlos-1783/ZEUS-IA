"""JX2: BD desechable para la suite de tests. Modulo puro (no importa `app`).

La suite nunca debe escribir en `backend/zeus.db` ni en una BD real (Postgres/Railway). El conftest
fija DATABASE_URL a un SQLite temporal unico por ejecucion ANTES de importar `app`, crea el esquema
con la misma rutina que usa la app al arrancar (`create_tables`: create_all + parches idempotentes),
valida el resultado y borra el directorio al terminar.
"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

PREFIJO_DIR = "zeus_tests_db_"
NOMBRE_FICHERO = "zeus_tests.db"


def _raiz_temporal() -> Path:
    return Path(tempfile.gettempdir()).resolve()


def ruta_sqlite_de_url(url: str) -> Optional[Path]:
    """Ruta del fichero de una URL sqlite de fichero; None si no es sqlite de fichero."""
    if not isinstance(url, str) or not url.lower().startswith("sqlite:///"):
        return None
    resto = url[len("sqlite:///"):].split("?")[0]
    if not resto or resto.startswith(":memory:"):
        return None
    try:
        return Path(resto).resolve()
    except (OSError, ValueError):
        return None


def validar_url_temporal(url: str, raiz_temporal: Optional[Path] = None) -> Optional[str]:
    """None si la URL es aceptable para tests; si no, el motivo del rechazo.

    Aceptable = sqlite de fichero dentro del directorio temporal del sistema, que no se llame zeus.db.
    """
    raiz = Path(raiz_temporal).resolve() if raiz_temporal else _raiz_temporal()
    ruta = ruta_sqlite_de_url(url)
    if ruta is None:
        return "la URL no es un sqlite de fichero (Postgres, memoria u otra BD): %r" % (str(url).split("@")[-1],)
    if ruta.name.lower() == "zeus.db":
        return "apunta a zeus.db (%s)" % ruta
    try:
        ruta.relative_to(raiz)
    except ValueError:
        return "el fichero %s no esta dentro del directorio temporal del sistema %s" % (ruta, raiz)
    return None


def preparar_url_de_tests() -> tuple:
    """Fija DATABASE_URL. Devuelve (directorio_creado_o_None, url).

    Un DATABASE_URL del entorno no se toca (se devuelve para que la salvaguarda lo valide: solo
    pasa si es un sqlite dentro del temporal del sistema). Sin variable se crea un directorio unico."""
    previa = os.environ.get("DATABASE_URL", "").strip()
    if previa:
        return None, previa
    directorio = Path(tempfile.mkdtemp(prefix=PREFIJO_DIR))
    url = "sqlite:///" + (directorio / NOMBRE_FICHERO).as_posix()
    os.environ["DATABASE_URL"] = url
    return directorio, url


def borrar_directorio(directorio: Optional[Path], intentos: int = 5, espera: float = 0.5) -> bool:
    """Borra el directorio temporal con reintentos (Windows bloquea ficheros abiertos).
    Nunca lanza: si no puede, avisa por stderr y devuelve False. Solo borra lo que creamos nosotros."""
    if directorio is None or not Path(directorio).exists():
        return True
    if not Path(directorio).name.startswith(PREFIJO_DIR):
        return True
    for i in range(intentos):
        try:
            shutil.rmtree(directorio)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(espera * (i + 1))
    shutil.rmtree(directorio, ignore_errors=True)
    if Path(directorio).exists():
        sys.stderr.write("[JX2] AVISO: no se pudo borrar la BD temporal %s\n" % directorio)
        return False
    return True
