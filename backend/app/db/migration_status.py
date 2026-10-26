"""Estado de migraciones Alembic para /health: revision aplicada en la BD frente a la head del codigo.

/health es publico (lo usa el healthcheck de Railway): aqui solo se exponen numeros de revision y, si algo
falla, el NOMBRE de la clase de error -- nunca el mensaje (puede llevar host/usuario de la BD) ni trazas.
"""
from __future__ import annotations

import ast
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _literal_revisions(value) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


@lru_cache(maxsize=1)
def code_heads() -> Tuple[str, ...]:
    """Head(s) de backend/alembic/versions segun el codigo desplegado.

    No se usa `alembic.script.ScriptDirectory`: dentro de la app la carpeta local `backend/alembic/` (con
    __init__.py) tapa al paquete alembic instalado (`import alembic.config` -> ModuleNotFoundError; ver la nota
    de scripts/alembic_conditional_stamp.py). Se hace lo mismo que ScriptDirectory.get_heads(): se leen
    `revision`/`down_revision` de cada migracion (ast, sin importar ni ejecutar nada) y la head es la revision
    a la que no apunta ninguna otra. Si una migracion apunta a una revision inexistente -> error."""
    revisions, downs = set(), set()
    versions = os.path.join(_BACKEND_ROOT, "alembic", "versions")
    for name in sorted(os.listdir(versions)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(versions, name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=name)
        found = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("revision", "down_revision"):
                    found[node.targets[0].id] = ast.literal_eval(node.value)
        if "revision" not in found:
            continue
        revisions.add(found["revision"])
        downs.update(_literal_revisions(found.get("down_revision")))
    missing = downs - revisions
    if missing:
        raise ValueError(f"down_revision inexistente: {sorted(missing)}")
    heads = tuple(sorted(revisions - downs))
    if not heads:
        raise ValueError("sin head")
    return heads


def _one_or_list(values: List[str]) -> Any:
    if not values:
        return None
    return values[0] if len(values) == 1 else values


def migration_status(engine: Engine) -> Dict[str, Any]:
    """{"current": revision en alembic_version, "head": revision del codigo, "up_to_date": bool}
    (+ "error": "<donde>: <ClaseDeError>" si no se pudo leer algo)."""
    out: Dict[str, Any] = {"current": None, "head": None, "up_to_date": False}
    try:
        heads = list(code_heads())
        out["head"] = _one_or_list(heads)
    except Exception as exc:
        logger.warning("migration_status: no se pudo leer la head del codigo (%s)", type(exc).__name__)
        out["error"] = f"head: {type(exc).__name__}"
        return out
    try:
        with engine.connect() as conn:
            if inspect(conn).has_table("alembic_version"):
                current = [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]
            else:
                current = []
    except Exception as exc:
        logger.warning("migration_status: no se pudo leer alembic_version (%s)", type(exc).__name__)
        out["error"] = f"db: {type(exc).__name__}"
        return out
    out["current"] = _one_or_list(sorted(current))
    out["up_to_date"] = bool(current) and sorted(current) == sorted(heads)
    return out
