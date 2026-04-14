#!/usr/bin/env python3
"""
Empresa piloto «Circo de Kan Roka»: aplica config/pilots/circo_kan_roka.json
(remediate + dueño Carmelo + Ana/Carlos en company_employees).

Requisitos: DATABASE_URL, migraciones al día, ya existe Company + user_companies
para el usuario titular (registro previo).

Uso (desde carpeta backend, venv activado):
  python scripts/seed_pilot_circo_kan_roka.py --company-id 2
  python scripts/seed_pilot_circo_kan_roka.py --slug-needle kan

Cuentas de empleado (TPV + control horario solamente en el front):
  set ZEUS_PILOT_SEED_PASSWORD=UnaClaveSegura1
  python scripts/seed_pilot_circo_kan_roka.py --company-id 2 --create-employee-logins

Antes, sustituye en config/pilots/circo_kan_roka.json los emails @example.com por
correos reales de Ana y Carlos (o crea usuarios a mano con dev_add_user.py).

Producción: en Railway activa ZEUS_CONTROL_HORARIO_DB_EMPLOYEES=true para listar
fichaje desde company_employees.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_JSON = BACKEND / "config" / "pilots" / "circo_kan_roka.json"


def _resolve_company_id(session, company_id: Optional[int], slug_needle: str) -> Optional[int]:
    from sqlalchemy import or_

    from app.models.company import Company

    if company_id is not None:
        c = session.query(Company).filter(Company.id == company_id).first()
        return c.id if c else None
    needle = f"%{slug_needle.strip()}%"
    if not needle.replace("%", ""):
        return None
    rows = (
        session.query(Company)
        .filter(or_(Company.slug.ilike(needle), Company.company_name.ilike(needle)))
        .order_by(Company.id.asc())
        .all()
    )
    if not rows:
        return None
    if len(rows) > 1:
        print("Varias empresas coinciden; elige --company-id:", file=sys.stderr)
        for r in rows:
            print(f"  id={r.id} slug={r.slug!r} name={r.company_name!r}", file=sys.stderr)
        return None
    return rows[0].id


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed piloto Circo de Kan Roka")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--company-id", type=int, default=None)
    g.add_argument("--slug-needle", default=None, help="Busca en slug o nombre (ej. kan)")
    parser.add_argument("--json-path", type=str, default=str(DEFAULT_JSON))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--create-employee-logins",
        action="store_true",
        help="Crea usuarios role=employee (requiere ZEUS_PILOT_SEED_PASSWORD)",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path)
    if not json_path.is_file():
        print(f"No existe JSON: {json_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(BACKEND))
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        slug = (args.slug_needle or "kan").strip()
        cid = _resolve_company_id(db, args.company_id, slug)
    finally:
        db.close()

    if not cid:
        print("No se pudo resolver company_id.", file=sys.stderr)
        return 1

    apply_script = BACKEND / "scripts" / "apply_pilot_company_data.py"
    cmd = [
        sys.executable,
        str(apply_script),
        "--company-id",
        str(cid),
        "--remediate",
        "--pilot",
        "--json",
        str(json_path),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    print("Ejecutando:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(BACKEND))
    if r.returncode != 0:
        return r.returncode

    if not args.create_employee_logins:
        print("Listo. Opcional: --create-employee-logins + ZEUS_PILOT_SEED_PASSWORD para cuentas Ana/Carlos.")
        return 0

    pwd = os.environ.get("ZEUS_PILOT_SEED_PASSWORD", "").strip()
    if len(pwd) < 8:
        print("Define ZEUS_PILOT_SEED_PASSWORD (≥8, mayúscula, minúscula, número).", file=sys.stderr)
        return 1

    import json

    blob = json.loads(json_path.read_text(encoding="utf-8"))
    logins = blob.get("employee_logins") or []
    if not isinstance(logins, list) or not logins:
        print("employee_logins vacío en JSON.", file=sys.stderr)
        return 1

    dev_add = BACKEND / "scripts" / "dev_add_user.py"
    for row in logins:
        if not isinstance(row, dict):
            continue
        email = str(row.get("email") or "").strip().lower()
        if not email:
            continue
        name = str(row.get("full_name") or "").strip()
        phone = str(row.get("phone") or "").strip() or "600000000"
        code = str(row.get("employee_code") or "").strip()
        if not code:
            print(f"Omitido (sin employee_code): {email}", file=sys.stderr)
            continue
        ucmd = [
            sys.executable,
            str(dev_add),
            email,
            pwd,
            "--full-name",
            name or email,
            "--phone",
            phone,
            "--role",
            "employee",
            "--link-company-id",
            str(cid),
            "--employee-code",
            code,
        ]
        print("Ejecutando:", " ".join(ucmd[:4]), "...")
        rr = subprocess.run(ucmd, cwd=str(BACKEND))
        if rr.returncode != 0:
            return rr.returncode

    print("Cuentas empleado creadas/vinculadas. Cambia contraseñas y emails @example.com en producción.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
