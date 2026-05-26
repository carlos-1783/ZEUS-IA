"""Utilidades para persistir JSON metadata en Company (SQLAlchemy)."""

from __future__ import annotations

import copy
from typing import Any, Dict

from sqlalchemy.orm.attributes import flag_modified


def set_company_metadata(company: Any, meta: Dict[str, Any]) -> None:
    """Asigna metadata y fuerza flush/commit (evita pérdida silenciosa en JSON/JSONB)."""
    company.metadata_ = copy.deepcopy(meta)
    flag_modified(company, "metadata_")
