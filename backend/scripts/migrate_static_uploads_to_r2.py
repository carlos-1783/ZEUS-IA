"""Migra los ficheros antiguos de STATIC_DIR/uploads a Cloudflare R2 (Fase 2 / Step 1).

POR DEFECTO NO ESCRIBE NADA (dry-run): lista que haria con cada fichero. Con --apply sube
cada fichero a R2 bajo `empresa/{company_id}/{categoria}/{file_id}/{nombre}` y crea su fila
en `stored_files` con `legacy_path = "uploads/<ruta>"`, de modo que las URLs antiguas
/static/uploads/... guardadas en BD siguen resolviendo (via /api/v1/upload/file/... y
los motores PERSEO) SOLO para usuarios de esa empresa.

No importa nada de `app`: funciona en cualquier contenedor con sqlalchemy + psycopg2 +
boto3 (`pip install boto3` si falta). No borra ningun fichero local.

Requisitos: migracion 0063 aplicada (tabla stored_files) y variables R2_* + DATABASE_URL.

Empresa de cada fichero (en este orden; si no hay una unica empresa, NO se migra y se
lista como "sin resolver"):
  1. Ruta con empresa: uploads/videos/<id>/..., uploads/videos/tenant_<id>/..., uploads/images/<id>/...
  2. Prefijo de usuario u<user_id>_ -> primera empresa del usuario.
  3. Referencias en BD al nombre del fichero (tpv_products.image, document_approvals,
     insurance_claims.documents, chat_messages) -> si todas apuntan a la misma empresa.

Uso:
  python scripts/migrate_static_uploads_to_r2.py --static-dir /data/static            # simulacion
  python scripts/migrate_static_uploads_to_r2.py --static-dir /data/static --apply    # migra
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import create_engine, inspect, text

_SAFE = re.compile(r"[^a-zA-Z0-9._-]")
_TENANT_PATH = re.compile(r"^(videos|images)/(?:tenant_)?(\d+)/")
_USER_PREFIX = re.compile(r"^u(\d+)_")
_CATEGORY = {"images": "images", "videos": "videos", "documents": "documents", "media": "media",
             "products": "products", "perseo": "images", "imagenes": "workspace",
             "documentos": "workspace"}
# (tabla, expresion de texto, expresion de empresa)
_REFERENCE_SOURCES = (
    ("tpv_products", "image", "company_id"),
    ("document_approvals", "document_payload_json", "company_id"),
    ("insurance_claims", "CAST(documents AS TEXT)", "company_id"),
    ("chat_messages", "message", "company_id"),
)


def _safe(name: str) -> str:
    return _SAFE.sub("_", Path(name).name).strip("._")[:150] or "fichero"


def _r2_client():
    import boto3
    from botocore.config import Config

    missing = [n for n in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET") if not os.getenv(n)]
    endpoint = os.getenv("R2_ENDPOINT_URL") or (
        f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com" if os.getenv("R2_ACCOUNT_ID") else ""
    )
    if not endpoint:
        missing.append("R2_ACCOUNT_ID (o R2_ENDPOINT_URL)")
    if missing:
        sys.exit("ERROR: faltan variables R2: " + ", ".join(missing))
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def _companies_referencing(conn, tables: Set[str], filename: str) -> Set[int]:
    found: Set[int] = set()
    for table, expr, company in _REFERENCE_SOURCES:
        if table not in tables:
            continue
        rows = conn.execute(
            text(f"SELECT DISTINCT {company} FROM {table} WHERE {expr} LIKE :pat AND {company} IS NOT NULL"),
            {"pat": f"%{filename}%"},
        ).fetchall()
        found.update(int(r[0]) for r in rows)
    return found


def _resolve(conn, tables: Set[str], rel: str, filename: str) -> Tuple[Optional[int], Optional[int], str]:
    """(company_id, user_id, motivo)."""
    m = _TENANT_PATH.match(rel)
    if m:
        cid = int(m.group(2))
        ok = conn.execute(text("SELECT 1 FROM companies WHERE id = :c"), {"c": cid}).first()
        return (cid, None, "ruta_empresa") if ok else (None, None, f"empresa {cid} de la ruta no existe")
    u = _USER_PREFIX.match(filename)
    if u:
        uid = int(u.group(1))
        row = conn.execute(
            text("SELECT company_id FROM user_companies WHERE user_id = :u ORDER BY id LIMIT 1"), {"u": uid}
        ).first()
        if row:
            return int(row[0]), uid, "prefijo_usuario"
        return None, uid, f"usuario {uid} sin empresa"
    refs = _companies_referencing(conn, tables, filename)
    if len(refs) == 1:
        return refs.pop(), None, "referencia_bd"
    if not refs:
        return None, None, "sin referencias en BD"
    return None, None, f"referenciado por varias empresas: {sorted(refs)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--static-dir", default=os.getenv("STATIC_DIR", "/data/static"))
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    ap.add_argument("--apply", action="store_true", help="Subir y registrar (sin esto: simulacion)")
    ap.add_argument("--report", default="", help="Ruta para guardar el informe JSON")
    args = ap.parse_args()

    uploads = Path(args.static_dir) / "uploads"
    if not uploads.is_dir():
        print(f"No existe {uploads}: nada que migrar.")
        return 0
    if not args.database_url:
        sys.exit("ERROR: falta DATABASE_URL")
    url = args.database_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    if "stored_files" not in tables:
        sys.exit("ERROR: falta la tabla stored_files: aplica antes la migracion 0063.")

    client = _r2_client() if args.apply else None
    bucket = os.getenv("R2_BUCKET", "")
    report: Dict[str, List[dict]] = {"migrado": [], "ya_migrado": [], "sin_resolver": [], "error": []}

    files = sorted(p for p in uploads.rglob("*") if p.is_file())
    print(f"{'APLICANDO' if args.apply else 'SIMULACION'}: {len(files)} ficheros en {uploads}")
    with engine.connect() as conn:
        for path in files:
            rel = path.relative_to(uploads).as_posix()
            legacy = f"uploads/{rel}"
            entry = {"legacy_path": legacy, "bytes": path.stat().st_size}
            if conn.execute(text("SELECT 1 FROM stored_files WHERE legacy_path = :l"), {"l": legacy}).first():
                report["ya_migrado"].append(entry)
                continue
            cid, uid, why = _resolve(conn, tables, rel, path.name)
            entry["motivo"] = why
            if cid is None:
                report["sin_resolver"].append(entry)
                continue
            category = _CATEGORY.get(rel.split("/", 1)[0], "media")
            file_id = uuid.uuid4().hex
            key = f"empresa/{cid}/{category}/{file_id}/{_safe(path.name)}"
            entry.update({"company_id": cid, "user_id": uid, "object_key": key})
            if not args.apply:
                report["migrado"].append(entry)
                continue
            try:
                data = path.read_bytes()
                ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                digest = hashlib.sha256(data).hexdigest()
                client.put_object(
                    Bucket=bucket, Key=key, Body=data, ContentType=ctype,
                    Metadata={"company-id": str(cid), "file-id": file_id, "sha256": digest, "legacy": "1"},
                )
                with conn.begin_nested() if conn.in_transaction() else conn.begin():
                    conn.execute(
                        text(
                            "INSERT INTO stored_files (id, company_id, user_id, category, object_key, "
                            "original_filename, content_type, size_bytes, sha256, legacy_path) VALUES "
                            "(:id, :c, :u, :cat, :k, :fn, :ct, :sz, :sha, :leg)"
                        ),
                        {"id": file_id, "c": cid, "u": uid, "cat": category, "k": key, "fn": path.name[:255],
                         "ct": ctype, "sz": len(data), "sha": digest, "leg": legacy},
                    )
                report["migrado"].append(entry)
            except Exception as exc:  # se informa y se sigue con el resto
                entry["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                report["error"].append(entry)
        if conn.in_transaction():
            conn.commit()

    for k, v in report.items():
        print(f"  {k}: {len(v)}")
    for e in report["sin_resolver"][:50]:
        print(f"    sin resolver: {e['legacy_path']} ({e['motivo']})")
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Informe: {args.report}")
    return 1 if report["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
