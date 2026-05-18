"""Importación CSV/XLSX de clientes al CRM (preview + confirm, archivos temporales, pandas)."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.customer import Customer
from app.models.user import User
from app.schemas.crm_import import CrmImportColumnMapping
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
PREVIEW_ROWS = 10
BATCH_SIZE = 500
TEMP_MAX_AGE_HOURS = 24

FIELD_ALIASES: Dict[str, List[str]] = {
    "name": ["nombre", "cliente", "full_name", "fullname", "name", "razon_social", "empresa", "contacto"],
    "email": ["email", "correo", "e_mail", "mail", "correo_electronico"],
    "phone": ["telefono", "tel", "movil", "mobile", "phone", "celular"],
    "notes": ["notas", "observaciones", "notes", "comentarios"],
    "tax_id": ["nif", "cif", "dni", "tax_id", "nif_cif", "identificacion"],
}


def _upload_root() -> Path:
    root = Path(settings.STATIC_DIR) / "tmp_uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _norm_header(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().replace(" ", "_").replace("-", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _norm_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    if len(digits) > 15:
        digits = digits[-15:]
    return f"+{digits}" if not digits.startswith("+") else digits


def _validate_email(value: Optional[str]) -> Optional[str]:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip().lower()
    try:
        return validate_email(raw, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def _meta_path(file_id: str) -> Path:
    return _upload_root() / f"{file_id}.meta.json"


def _data_path(file_id: str, ext: str) -> Path:
    return _upload_root() / f"{file_id}{ext}"


def _allowed_ext(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        return ".csv"
    if lower.endswith(".xlsx"):
        return ".xlsx"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Formato no soportado. Usa CSV o XLSX.",
    )


def save_upload(content: bytes, filename: str, user_id: int) -> str:
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo supera el límite de {MAX_FILE_BYTES // (1024 * 1024)} MB.",
        )
    ext = _allowed_ext(filename)
    file_id = uuid.uuid4().hex
    data_path = _data_path(file_id, ext)
    data_path.write_bytes(content)
    meta = {
        "file_id": file_id,
        "filename": filename,
        "ext": ext,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _meta_path(file_id).write_text(json.dumps(meta), encoding="utf-8")
    return file_id


def _load_meta(file_id: str, user_id: int) -> Dict[str, Any]:
    meta_file = _meta_path(file_id)
    if not meta_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de importación no encontrada o expirada.")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if meta.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este archivo de importación.")
    return meta


def _read_dataframe(file_id: str, user_id: int) -> Tuple[pd.DataFrame, str]:
    meta = _load_meta(file_id, user_id)
    path = _data_path(file_id, meta["ext"])
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo temporal no encontrado.")
    filename = meta.get("filename") or "import"
    try:
        if meta["ext"] == ".csv":
            df = None
            for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
                try:
                    df = pd.read_csv(path, encoding=encoding, dtype=str, nrows=MAX_ROWS + 1)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pudo leer el CSV (codificación no reconocida).",
                )
        else:
            df = pd.read_excel(path, dtype=str, engine="openpyxl")
            if len(df) > MAX_ROWS:
                df = df.iloc[:MAX_ROWS]
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("pandas read failed file_id=%s: %s", file_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo leer el archivo. Comprueba que sea un CSV o XLSX válido.",
        ) from exc

    if df is None or df.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo no tiene datos.")

    df = df.fillna("")
    df.columns = [_norm_header(c) or f"column_{i + 1}" for i, c in enumerate(df.columns)]
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df, filename


def delete_upload(file_id: str) -> None:
    try:
        meta_file = _meta_path(file_id)
        if meta_file.is_file():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            _data_path(file_id, meta.get("ext", ".csv")).unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("cleanup upload %s: %s", file_id, exc)


def detect_column_mapping(columns: List[str]) -> CrmImportColumnMapping:
    col_set = set(columns)
    mapping: Dict[str, Optional[str]] = {
        "name": None,
        "email": None,
        "phone": None,
        "notes": None,
        "tax_id": None,
    }
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            key = _norm_header(alias)
            if key in col_set:
                mapping[field] = key
                break
    return CrmImportColumnMapping(**mapping)


def _pick_row(row: pd.Series, col: Optional[str]) -> Optional[str]:
    if not col or col not in row.index:
        return None
    v = str(row[col]).strip()
    return v or None


def _map_row(row: pd.Series, mapping: CrmImportColumnMapping) -> Dict[str, Optional[str]]:
    name = _pick_row(row, mapping.name)
    email_raw = _pick_row(row, mapping.email)
    phone_raw = _pick_row(row, mapping.phone)
    notes = _pick_row(row, mapping.notes)
    tax_id = _pick_row(row, mapping.tax_id)

    email = _validate_email(email_raw) if email_raw else None
    phone = _norm_phone(phone_raw)
    if tax_id:
        tax_id = re.sub(r"\s+", "", tax_id)[:50] or None

    return {
        "name": name[:100] if name else None,
        "email": email,
        "phone": phone[:20] if phone else None,
        "notes": notes,
        "tax_id": tax_id,
    }


def build_preview(file_id: str, user_id: int) -> Tuple[str, List[str], CrmImportColumnMapping, List[Dict[str, Any]], int, str]:
    df, filename = _read_dataframe(file_id, user_id)
    columns = list(df.columns)
    if not columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se detectaron columnas.")

    suggested = detect_column_mapping(columns)
    if not suggested.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se detectó columna de nombre. Usa una cabecera como «nombre» o «cliente».",
        )

    preview: List[Dict[str, Any]] = []
    for _, row in df.head(PREVIEW_ROWS).iterrows():
        preview.append(_map_row(row, suggested))

    return file_id, columns, suggested, preview, len(df), filename


def store_preview_from_upload(content: bytes, filename: str, user: User) -> str:
    file_id = save_upload(content, filename, user.id)
    return file_id


def _existing_email_phone_sets(db: Session, company_id: Optional[int]) -> Tuple[Set[str], Set[str]]:
    emails: Set[str] = set()
    phones: Set[str] = set()
    q = db.query(Customer.email, Customer.phone)
    if company_id is not None:
        q = q.filter(Customer.company_id == company_id)
    else:
        q = q.filter(Customer.company_id.is_(None))
    for email, phone in q.all():
        if email:
            emails.add(str(email).strip().lower())
        norm = _norm_phone(phone)
        if norm:
            phones.add(norm)
    return emails, phones


def confirm_import(
    db: Session,
    user: User,
    *,
    file_id: str,
    mapping: CrmImportColumnMapping,
) -> Dict[str, Any]:
    if not mapping.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar la columna de nombre en el mapeo.",
        )

    df, filename = _read_dataframe(file_id, user.id)
    if mapping.name not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La columna «{mapping.name}» no existe en el archivo.",
        )

    company_id = crm_svc.primary_company_id(db, user)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere una empresa asociada para importar clientes.",
        )

    existing_emails, existing_phones = _existing_email_phone_sets(db, company_id)
    batch_emails: Set[str] = set()
    batch_phones: Set[str] = set()

    to_insert: List[Customer] = []
    skipped_empty = 0
    skipped_duplicates = 0
    skipped_invalid = 0
    errors: List[str] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2 if isinstance(idx, (int, float)) else len(to_insert) + 2
        mapped = _map_row(row, mapping)

        if not mapped.get("name"):
            skipped_empty += 1
            continue

        name = mapped["name"]
        if len(name) < 2:
            skipped_invalid += 1
            if len(errors) < 20:
                errors.append(f"Fila {row_num}: nombre demasiado corto.")
            continue

        email = mapped.get("email")
        phone = mapped.get("phone")

        if email and (email in existing_emails or email in batch_emails):
            skipped_duplicates += 1
            continue
        if phone and (phone in existing_phones or phone in batch_phones):
            skipped_duplicates += 1
            continue

        to_insert.append(
            Customer(
                name=name,
                email=email,
                phone=phone,
                tax_id=mapped.get("tax_id"),
                notes=mapped.get("notes"),
                is_active=True,
                is_company=True,
                company_id=company_id,
                owner_user_id=user.id,
            )
        )
        if email:
            batch_emails.add(email)
            existing_emails.add(email)
        if phone:
            batch_phones.add(phone)
            existing_phones.add(phone)

    imported = len(to_insert)
    skipped = skipped_empty + skipped_duplicates + skipped_invalid

    if imported == 0:
        delete_upload(file_id)
        return {
            "success": True,
            "imported": 0,
            "skipped": skipped,
            "skipped_empty": skipped_empty,
            "skipped_duplicates": skipped_duplicates,
            "skipped_invalid": skipped_invalid,
            "errors": errors,
            "message": "No se importó ningún cliente (filas vacías, duplicadas o inválidas).",
        }

    try:
        for start in range(0, imported, BATCH_SIZE):
            db.bulk_save_objects(to_insert[start : start + BATCH_SIZE])
        db.flush()
        crm_svc.log_activity(
            db,
            company_id=company_id,
            user_id=user.id,
            customer_id=None,
            record_id=None,
            action="customers_imported",
            summary=f"Importación masiva: {imported} cliente(s) desde {filename}",
            payload={
                "file_id": file_id,
                "filename": filename,
                "imported": imported,
                "skipped_duplicates": skipped_duplicates,
                "skipped_empty": skipped_empty,
                "skipped_invalid": skipped_invalid,
            },
            commit=False,
        )
        db.commit()
        logger.info("crm import ok user=%s imported=%s skipped=%s", user.id, imported, skipped)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("confirm_import failed file_id=%s", file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al importar: {exc}",
        ) from exc
    finally:
        delete_upload(file_id)

    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "skipped_empty": skipped_empty,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
        "errors": errors,
        "message": f"Importados {imported} cliente(s). Omitidas {skipped} fila(s).",
    }
