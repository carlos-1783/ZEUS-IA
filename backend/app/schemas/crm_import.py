"""Esquemas importación masiva de clientes CRM."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CrmImportColumnMapping(BaseModel):
    """Mapeo columna archivo → campo Zeus (null = no importar)."""

    name: Optional[str] = Field(None, description="Columna del archivo para nombre")
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    tax_id: Optional[str] = None


class CrmImportPreviewOut(BaseModel):
    success: bool = True
    columns: List[str] = []
    suggested_mapping: CrmImportColumnMapping
    preview_rows: List[Dict[str, Any]] = []
    total_rows: int = 0
    filename: str = ""


class CrmImportResultOut(BaseModel):
    success: bool = True
    imported: int = 0
    skipped: int = 0
    skipped_empty: int = 0
    skipped_duplicates: int = 0
    skipped_invalid: int = 0
    errors: List[str] = Field(default_factory=list)
    message: str = ""
