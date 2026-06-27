"""THALOS v1 — backup real (sqlite copy or postgres pg_dump)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.core.config import settings
from services.automation import utils


def create_backup(*, activity_id: Optional[int] = None) -> Dict[str, Any]:
    """Real DB backup: sqlite file copy or postgres pg_dump."""
    backup_dir = Path(os.getenv("AGENT_BACKUP_DIR", "storage/backups"))
    utils.ensure_dir(backup_dir)
    ts = utils.timestamp()
    db_url = settings.DATABASE_URL or ""
    backup_created = False
    backup_path: Optional[str] = None
    method = "none"

    if "sqlite" in db_url.lower():
        source = Path(db_url.replace("sqlite:///", "").split("?")[0])
        if not source.is_absolute():
            source = Path.cwd() / source
        if source.exists():
            target = backup_dir / f"zeus_backup_{ts}.db"
            shutil.copy2(source, target)
            backup_created = True
            backup_path = str(target.resolve())
            method = "sqlite_copy"
    elif "postgres" in db_url.lower():
        target = backup_dir / f"zeus_backup_{ts}.sql"
        try:
            parsed = urlparse(db_url)
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
            host = parsed.hostname or "localhost"
            port = str(parsed.port or 5432)
            user = parsed.username or "postgres"
            dbname = (parsed.path or "/postgres").lstrip("/")
            cmd = [
                "pg_dump",
                "-h", host,
                "-p", port,
                "-U", user,
                "-d", dbname,
                "-f", str(target),
                "--no-owner",
                "--no-acl",
            ]
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            if proc.returncode == 0 and target.exists() and target.stat().st_size > 0:
                backup_created = True
                backup_path = str(target.resolve())
                method = "pg_dump"
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            return {
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "backup_created": False,
                "backup_path": None,
                "method": "pg_dump_failed",
                "activity_id": activity_id,
                "notes": f"pg_dump unavailable: {exc}. Use Railway Postgres backups.",
            }
    else:
        source = Path("zeus.db")
        if source.exists():
            target = backup_dir / f"zeus_backup_{ts}.db"
            shutil.copy2(source, target)
            backup_created = True
            backup_path = str(target.resolve())
            method = "sqlite_fallback"

    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "backup_created": backup_created,
        "backup_path": backup_path,
        "method": method,
        "activity_id": activity_id,
        "notes": (
            f"Backup THALOS ({method}) generado."
            if backup_created
            else "Backup no disponible — configure pg_dump o zeus.db local."
        ),
    }
