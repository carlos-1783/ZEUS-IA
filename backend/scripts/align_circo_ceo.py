#!/usr/bin/env python3
"""
Alinea cuenta CEO + empresa piloto Circo de Kan Roka para entorno real.

Hace en una sola ejecución (idempotente):
- Crea/actualiza usuario CEO (owner, activo, password hash).
- Resuelve/crea empresa Circo de Kan Roka.
- Garantiza vínculo user_companies (company_admin).
- Aplica parche piloto (company + owner_employee + employees extra) desde JSON.

Uso (en Railway shell o entorno con DATABASE_URL):
  python scripts/align_circo_ceo.py \
    --email "elcirkocanroca@gmail.com" \
    --password "CircoKanroka26!"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.company import Company, UserCompany
from app.models.user import User


def _slugify(v: str) -> str:
    s = (v or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "empresa"


def _candidate_company(db, company_name: str, user: User) -> Optional[Company]:
    # 1) Si ya tiene empresa vinculada, preferir esa.
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if link:
        c = db.query(Company).filter(Company.id == link.company_id).first()
        if c:
            return c
    # 2) Buscar por slug/nombre de piloto.
    needles = ("%circo%", "%kanroka%", "%kan-roka%", "%can-roca%")
    for n in needles:
        c = (
            db.query(Company)
            .filter((Company.slug.ilike(n)) | (Company.company_name.ilike(n)))
            .order_by(Company.id.asc())
            .first()
        )
        if c:
            return c
    # 3) Buscar por nombre exacto deseado.
    c = db.query(Company).filter(Company.company_name == company_name).first()
    return c


def _ensure_company(db, company_name: str) -> Company:
    base = _slugify(company_name)
    slug = base
    idx = 1
    while db.query(Company).filter(Company.slug == slug).first():
        idx += 1
        slug = f"{base}-{idx}"
    c = Company(
        company_name=company_name[:255],
        slug=slug[:100],
        pilot_company=True,
        status="active",
        sector="restaurante",
        country="ES",
        currency="EUR",
        metadata_={"source": "align_circo_ceo_script", "billing_enabled": False, "onboarding_completed": True},
    )
    db.add(c)
    db.flush()
    return c


def _apply_json_patch(db, company_id: int, user_id: int, json_path: Path) -> Dict[str, Any]:
    from scripts.apply_pilot_company_data import main as _unused  # noqa: F401
    from app.models.company_employee import CompanyEmployee

    blob = json.loads(json_path.read_text(encoding="utf-8"))
    report: Dict[str, Any] = {"applied": []}

    company = db.query(Company).filter(Company.id == company_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not company or not user:
        return {"error": "company/user no encontrado"}

    company_blob = blob.get("company") if isinstance(blob.get("company"), dict) else {}
    if company_blob:
        company.company_name = str(company_blob.get("company_name") or company.company_name)[:255]
        company.sector = str(company_blob.get("sector") or company.sector or "")[:100] or None
        company.pilot_company = bool(company_blob.get("pilot_company", True))
        company.country = str(company_blob.get("country") or company.country or "ES")[:10]
        company.currency = str(company_blob.get("currency") or company.currency or "EUR")[:10]
        db.add(company)
        report["applied"].append("company_patch")

    user.company_name = company.company_name[:255]
    user.role = "owner"
    user.is_active = True
    db.add(user)
    report["applied"].append("user_company_name_role")

    owner = blob.get("owner_employee") if isinstance(blob.get("owner_employee"), dict) else {}
    owner_code = f"U{user.id}-OWNER"
    own = (
        db.query(CompanyEmployee)
        .filter(CompanyEmployee.company_id == company.id, CompanyEmployee.employee_code == owner_code)
        .first()
    )
    if not own:
        own = CompanyEmployee(
            company_id=company.id,
            user_id=user.id,
            employee_code=owner_code,
            full_name=(owner.get("full_name") or user.full_name or user.email)[:255],
            phone=str(owner.get("phone") or user.phone or "")[:32] or None,
            role_title=str(owner.get("role_title") or "owner")[:100],
            is_active=True,
            source="align_circo_ceo",
        )
        db.add(own)
        report["applied"].append("owner_employee_insert")
    else:
        own.user_id = user.id
        own.full_name = str(owner.get("full_name") or own.full_name)[:255]
        own.phone = str(owner.get("phone") or own.phone or "")[:32] or None
        own.role_title = str(owner.get("role_title") or own.role_title or "owner")[:100]
        own.is_active = True
        db.add(own)
        report["applied"].append("owner_employee_update")

    extras = blob.get("company_employees_extra") if isinstance(blob.get("company_employees_extra"), list) else []
    for row in extras:
        if not isinstance(row, dict):
            continue
        code = str(row.get("employee_code") or "").strip()
        name = str(row.get("full_name") or "").strip()
        if not code or not name:
            continue
        ce = (
            db.query(CompanyEmployee)
            .filter(CompanyEmployee.company_id == company.id, CompanyEmployee.employee_code == code)
            .first()
        )
        if not ce:
            ce = CompanyEmployee(
                company_id=company.id,
                user_id=None,
                employee_code=code,
                full_name=name[:255],
                phone=str(row.get("phone") or "")[:32] or None,
                role_title=str(row.get("role_title") or "employee")[:100],
                is_active=True,
                source="align_circo_ceo",
            )
            db.add(ce)
            report["applied"].append(f"employee_insert:{code}")
        else:
            ce.full_name = name[:255]
            ce.phone = str(row.get("phone") or ce.phone or "")[:32] or None
            ce.role_title = str(row.get("role_title") or ce.role_title or "employee")[:100]
            ce.is_active = True
            db.add(ce)
            report["applied"].append(f"employee_update:{code}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Alinear CEO y empresa piloto Circo de Kan Roka")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Carmelo Martin Garcia")
    parser.add_argument("--phone", default="604173491")
    parser.add_argument("--company-name", default="Circo de Kan Roka")
    parser.add_argument(
        "--json-path",
        default=str(Path(__file__).resolve().parent.parent / "config" / "pilots" / "circo_kan_roka.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        email = args.email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name=args.full_name[:255],
                phone=args.phone[:32],
                hashed_password=get_password_hash(args.password),
                is_active=True,
                is_superuser=False,
                role="owner",
                company_name=args.company_name[:255],
            )
            db.add(user)
            db.flush()
            user_action = "user_created"
        else:
            user.full_name = args.full_name[:255]
            user.phone = args.phone[:32]
            user.hashed_password = get_password_hash(args.password)
            user.role = "owner"
            user.is_active = True
            user.company_name = args.company_name[:255]
            db.add(user)
            db.flush()
            user_action = "user_updated"

        company = _candidate_company(db, args.company_name, user)
        if not company:
            company = _ensure_company(db, args.company_name)
            company_action = "company_created"
        else:
            company_action = "company_reused"

        link = (
            db.query(UserCompany)
            .filter(UserCompany.user_id == user.id, UserCompany.company_id == company.id)
            .first()
        )
        if not link:
            db.add(UserCompany(user_id=user.id, company_id=company.id, role="company_admin"))
            link_action = "user_company_link_created"
        else:
            link.role = "company_admin"
            db.add(link)
            link_action = "user_company_link_updated"

        report = _apply_json_patch(db, company.id, user.id, Path(args.json_path))
        out = {
            "success": "error" not in report,
            "database_url_present": bool(os.getenv("DATABASE_URL")),
            "user_action": user_action,
            "company_action": company_action,
            "link_action": link_action,
            "user_id": user.id,
            "company_id": company.id,
            "company_name": company.company_name,
            "details": report,
            "dry_run": bool(args.dry_run),
        }
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0 if out["success"] else 1
    except Exception as e:
        db.rollback()
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
