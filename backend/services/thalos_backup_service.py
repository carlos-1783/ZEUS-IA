"""THALOS — copia de seguridad real de la base de datos a almacenamiento externo.

Fase 2 / Step 1:
- Postgres: `pg_dump` a un fichero temporal, subido a R2 bajo `plataforma/backups/`
  (fuera de cualquier prefijo de empresa: contiene datos de todas) y borrado en local.
- SQLite (solo desarrollo): copia del fichero configurado en DATABASE_URL.
- Antes la copia se dejaba en storage/backups (disco efimero de Railway: desaparecia en
  el siguiente deploy) y, sin Postgres, se copiaba `zeus.db` del repo aunque no fuera la
  base en uso. Ya no: sin pg_dump o sin R2 la copia FALLA y lo dice.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from app.core.config import settings


def _result(created: bool, method: str, activity_id: Optional[int], notes: str, **extra: Any) -> Dict[str, Any]:
    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "backup_created": created,
        "method": method,
        "activity_id": activity_id,
        "notes": notes,
        **extra,
    }


def _pg_dump(db_url: str, target: Path) -> None:
    parsed = urlparse(db_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    cmd = [
        shutil.which("pg_dump") or "pg_dump",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", unquote(parsed.username or "postgres"),
        "-d", (parsed.path or "/postgres").lstrip("/"),
        "-f", str(target),
        "--no-owner",
        "--no-acl",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        # stderr de pg_dump no lleva la contrasena (va por PGPASSWORD), pero se recorta.
        raise RuntimeError(f"pg_dump fallo (codigo {proc.returncode}): {(proc.stderr or '').strip()[:300]}")


def create_backup(*, activity_id: Optional[int] = None) -> Dict[str, Any]:
    from services import object_storage

    if not object_storage.is_configured():
        return _result(
            False, "none", activity_id,
            "Copia no realizada: almacenamiento externo (R2) sin configurar. Una copia en el "
            "disco de Railway se perderia en el siguiente deploy.",
            missing=object_storage.missing_config(),
        )

    db_url = settings.DATABASE_URL or ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory(prefix="thalos_backup_") as tmp:
        if db_url.lower().startswith("postgres"):
            method = "pg_dump"
            target = Path(tmp) / f"zeus_backup_{ts}.sql"
            if shutil.which("pg_dump") is None:
                return _result(False, method, activity_id, "pg_dump no esta instalado en el contenedor.")
            try:
                _pg_dump(db_url, target)
            except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
                return _result(False, method, activity_id, str(exc)[:400])
            content_type = "application/sql"
        elif db_url.lower().startswith("sqlite"):
            method = "sqlite_copy"
            source = Path(db_url.split("///", 1)[-1].split("?", 1)[0])
            if not source.is_absolute():
                source = Path.cwd() / source
            if not source.is_file():
                return _result(False, method, activity_id, f"No existe la base SQLite configurada: {source.name}")
            target = Path(tmp) / f"zeus_backup_{ts}.db"
            shutil.copy2(source, target)
            content_type = "application/vnd.sqlite3"
        else:
            return _result(False, "unsupported", activity_id, "Motor de base de datos no soportado para copia.")

        data = target.read_bytes()
        try:
            key = object_storage.store_platform_object(f"backups/{target.name}", data, content_type)
        except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
            return _result(False, method, activity_id, f"No se pudo subir la copia: {exc}")

    return _result(
        True, method, activity_id, f"Copia ({method}) guardada en almacenamiento externo.",
        storage_key=key, size_bytes=len(data),
    )
