"""THALOS v1 — backup real (wrapper sobre lógica existente)."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.automation import utils


def create_backup(*, activity_id: Optional[int] = None) -> Dict[str, Any]:
    """Copia zeus.db local si existe (misma lógica que automation handler)."""
    source = Path("zeus.db")
    backup_dir = Path(os.getenv("AGENT_BACKUP_DIR", "storage/backups"))
    utils.ensure_dir(backup_dir)

    backup_created = False
    backup_path: Optional[str] = None

    if source.exists():
        target = backup_dir / f"zeus_backup_{utils.timestamp()}.db"
        shutil.copy2(source, target)
        backup_created = True
        backup_path = str(target.resolve())

    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "source_exists": source.exists(),
        "backup_created": backup_created,
        "backup_path": backup_path,
        "activity_id": activity_id,
        "notes": (
            "Backup THALOS v1 generado."
            if backup_created
            else "Sin zeus.db local; en Railway usar backup de Postgres gestionado."
        ),
    }
