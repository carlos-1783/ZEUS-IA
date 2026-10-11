"""Almacenamiento de objetos comun del nucleo (Cloudflare R2 via API S3).

Fase 2 / Step 1 (hallazgos C1 y A2):
- El binario NUNCA toca el disco local ni /static: va a R2 bajo
  `empresa/{company_id}/{categoria}/{file_id}/{nombre}`.
- `stored_files` registra a que empresa pertenece cada objeto; todo acceso se resuelve
  contra esa fila (filtro de empresa) y se entrega con una URL firmada de vida corta.
- Sin credenciales R2 la app arranca igual: las operaciones lanzan
  `StorageNotConfigured`, que los endpoints convierten en un 503 explicito. No hay
  ningun "modo local" de respaldo: eso volveria a perder ficheros en cada deploy.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.stored_file import StoredFile

logger = logging.getLogger(__name__)

CATEGORIES = frozenset(
    {"images", "videos", "documents", "media", "products", "crm_import", "workspace", "inbox"}
)
# Tipos que el navegador puede mostrar en linea; el resto se entrega como descarga.
_INLINE_PREFIXES = ("image/", "video/")
_INLINE_TYPES = frozenset({"application/pdf"})
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]")


class StorageNotConfigured(RuntimeError):
    """Faltan variables R2: la operacion no se puede hacer (503 en la API)."""

    def __init__(self, missing: List[str]):
        self.missing = missing
        super().__init__(
            "Almacenamiento de ficheros no configurado (Cloudflare R2). Faltan: " + ", ".join(missing)
        )


class StorageError(RuntimeError):
    """Fallo real hablando con R2 (red, credenciales, bucket)."""


class ContentMismatch(ValueError):
    """El contenido no corresponde al tipo declarado."""


# ------------------------------------------------------------------ configuracion


def missing_config() -> List[str]:
    missing = [
        name
        for name in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
        if not getattr(settings, name, "")
    ]
    if not getattr(settings, "R2_ENDPOINT_URL", "") and not getattr(settings, "R2_ACCOUNT_ID", ""):
        missing.append("R2_ACCOUNT_ID (o R2_ENDPOINT_URL)")
    return missing


def is_configured() -> bool:
    return not missing_config()


def _endpoint_url() -> str:
    explicit = getattr(settings, "R2_ENDPOINT_URL", "")
    if explicit:
        return explicit
    return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


def _build_client() -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


_client_cache: Optional[Any] = None


def _client() -> Any:
    global _client_cache
    missing = missing_config()
    if missing:
        raise StorageNotConfigured(missing)
    if _client_cache is None:
        _client_cache = _build_client()
    return _client_cache


def reset_client_cache() -> None:
    global _client_cache
    _client_cache = None


# ------------------------------------------------------------------ validacion


def safe_filename(name: str, default: str = "fichero") -> str:
    base = PurePosixPath((name or "").replace("\\", "/")).name
    base = _SAFE_NAME_RE.sub("_", base).strip("._")[:150]
    return base or default


def _sniff(data: bytes) -> Optional[str]:
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        return "video/quicktime" if brand == b"qt  " else "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    return None


_ZIP_BASED = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
_TEXT_TYPES = frozenset({"text/plain", "text/csv"})


def verify_content(data: bytes, declared: str) -> None:
    """Rechaza ficheros cuyo contenido no corresponde al tipo declarado (p. ej. un HTML
    renombrado a .png). Solo se aceptan tipos que sabemos verificar."""
    declared = (declared or "").split(";")[0].strip().lower()
    sniffed = _sniff(data)
    if declared in _TEXT_TYPES:
        if b"\x00" in data[:65536]:
            raise ContentMismatch("El fichero de texto contiene datos binarios.")
        return
    if declared in _ZIP_BASED:
        if sniffed != "application/zip":
            raise ContentMismatch("El fichero no es un documento Office valido.")
        return
    if declared == "video/quicktime" and sniffed == "video/mp4":
        return  # QuickTime con marca isom/mp42: mismo contenedor
    if sniffed != declared:
        raise ContentMismatch(f"El contenido no corresponde al tipo declarado ({declared}).")


# ------------------------------------------------------------------ operaciones


def build_object_key(company_id: int, category: str, file_id: str, filename: str) -> str:
    return f"empresa/{int(company_id)}/{category}/{file_id}/{safe_filename(filename)}"


def _assert_key_scope(row: StoredFile) -> None:
    # Defensa en profundidad: la fila y la clave deben apuntar a la misma empresa.
    if not row.object_key.startswith(f"empresa/{int(row.company_id)}/"):
        raise StorageError(f"Clave de objeto fuera del ambito de su empresa (file_id={row.id}).")


def store_file(
    db: Session,
    *,
    company_id: Optional[int],
    user_id: Optional[int],
    category: str,
    filename: str,
    content_type: str,
    data: bytes,
    legacy_path: Optional[str] = None,
) -> StoredFile:
    """Sube a R2 y registra la fila. Si el registro en BD falla, borra el objeto subido."""
    if not isinstance(company_id, int):
        raise ValueError("Se requiere una empresa para guardar ficheros.")
    if category not in CATEGORIES:
        raise ValueError(f"Categoria de fichero no valida: {category}")
    if not data:
        raise ValueError("El fichero esta vacio.")

    client = _client()  # StorageNotConfigured antes de hacer nada
    file_id = uuid.uuid4().hex
    key = build_object_key(company_id, category, file_id, filename)
    ctype = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    digest = hashlib.sha256(data).hexdigest()
    try:
        client.put_object(
            Bucket=settings.R2_BUCKET,
            Key=key,
            Body=data,
            ContentType=ctype,
            Metadata={"company-id": str(company_id), "file-id": file_id, "sha256": digest},
        )
    except Exception as exc:  # botocore ClientError / EndpointConnectionError
        logger.error("R2 put_object fallo key=%s: %s", key, type(exc).__name__)
        raise StorageError("No se pudo guardar el fichero en el almacenamiento externo.") from exc

    row = StoredFile(
        id=file_id,
        company_id=company_id,
        user_id=user_id,
        category=category,
        object_key=key,
        original_filename=(filename or "fichero")[:255],
        content_type=ctype,
        size_bytes=len(data),
        sha256=digest,
        legacy_path=legacy_path,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        try:
            client.delete_object(Bucket=settings.R2_BUCKET, Key=key)
        except Exception:
            logger.exception("R2: no se pudo borrar el objeto huerfano %s", key)
        raise
    logger.info(
        "R2 fichero guardado file_id=%s company_id=%s category=%s bytes=%s",
        file_id, company_id, category, len(data),
    )
    return row


def get_legacy_for_companies(
    db: Session, legacy_path: str, company_ids: Iterable[int]
) -> Optional[StoredFile]:
    """Fichero migrado desde STATIC_DIR, solo si pertenece a una de las empresas indicadas."""
    ids = [int(c) for c in company_ids if c is not None]
    if not ids or not legacy_path:
        return None
    return (
        db.query(StoredFile)
        .filter(
            StoredFile.legacy_path == legacy_path,
            StoredFile.company_id.in_(ids),
            StoredFile.deleted_at.is_(None),
        )
        .first()
    )


def get_for_companies(db: Session, file_id: str, company_ids: Iterable[int]) -> Optional[StoredFile]:
    """La fila solo si pertenece a una de las empresas indicadas y no esta borrada."""
    ids = [int(c) for c in company_ids if c is not None]
    if not ids or not file_id or not re.fullmatch(r"[0-9a-f]{32}", file_id):
        return None
    return (
        db.query(StoredFile)
        .filter(
            StoredFile.id == file_id,
            StoredFile.company_id.in_(ids),
            StoredFile.deleted_at.is_(None),
        )
        .first()
    )


def signed_url(row: StoredFile, *, ttl: Optional[int] = None) -> str:
    _assert_key_scope(row)
    client = _client()
    ctype = row.content_type or "application/octet-stream"
    inline = ctype.startswith(_INLINE_PREFIXES) or ctype in _INLINE_TYPES
    disposition = f'{"inline" if inline else "attachment"}; filename="{safe_filename(row.original_filename)}"'
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.R2_BUCKET,
                "Key": row.object_key,
                "ResponseContentType": ctype,
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=int(ttl or settings.R2_SIGNED_URL_TTL_SEC),
        )
    except Exception as exc:
        raise StorageError("No se pudo firmar la URL del fichero.") from exc


def read_bytes(row: StoredFile) -> bytes:
    _assert_key_scope(row)
    client = _client()
    try:
        obj = client.get_object(Bucket=settings.R2_BUCKET, Key=row.object_key)
        return obj["Body"].read()
    except Exception as exc:
        raise StorageError("No se pudo leer el fichero del almacenamiento externo.") from exc


def delete_file(db: Session, row: StoredFile) -> None:
    """Borra el objeto en R2 y marca la fila (queda el rastro de que existio)."""
    _assert_key_scope(row)
    client = _client()
    try:
        client.delete_object(Bucket=settings.R2_BUCKET, Key=row.object_key)
    except Exception as exc:
        raise StorageError("No se pudo borrar el fichero del almacenamiento externo.") from exc
    row.deleted_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()


def file_url(row: StoredFile) -> str:
    """URL estable que se guarda en BD: el acceso real siempre pasa por la API."""
    return f"/api/v1/files/{row.id}"
