#!/usr/bin/env python3
"""
Aplica datos del piloto en BD: usuario titular, fila companies, empleado titular (U{id}-OWNER).

Uso (desde backend/, venv y DATABASE_URL):
  python scripts/apply_pilot_company_data.py --company-id 2 --full-name "Juan Pérez" --phone "+34..." \\
    --company-name "El Circo Can Roca" --sector restaurante --pilot \\
    --owner-name "Juan Pérez" --owner-phone "+34..."

  python scripts/apply_pilot_company_data.py --company-id 2 --json datos_piloto.json

  # Primero dejar stack listo (empleado, TPV demo, fiscal), luego rellenar nombres:
  python scripts/apply_pilot_company_data.py --company-id 2 --remediate --pilot --json datos_piloto.json

No sustituye al cliente: ejecútalo tú donde apunte DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aplicar datos de empresa piloto (usuario, company, company_employee titular)"
    )
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Usuario titular; por defecto el primero en user_companies de esa empresa",
    )
    parser.add_argument("--json", dest="json_path", default=None, help="Archivo JSON (user, company, owner_employee)")
    parser.add_argument("--full-name", default=None)
    parser.add_argument("--phone", default=None)
    parser.add_argument("--company-name", default=None)
    parser.add_argument("--sector", default=None)
    parser.add_argument("--pilot", action="store_true", help="pilot_company=True")
    parser.add_argument("--no-pilot", action="store_true", help="pilot_company=False")
    parser.add_argument("--owner-name", default=None)
    parser.add_argument("--owner-phone", default=None)
    parser.add_argument("--owner-role", default=None, help="role_title del titular en company_employees")
    parser.add_argument(
        "--remediate",
        action="store_true",
        help="Llamar remediate_existing_company antes (requiere migraciones al día)",
    )
    parser.add_argument("--business-type", default="restaurant", help="Solo con --remediate")
    parser.add_argument("--no-fiscal-seed", action="store_true", help="Con --remediate: no crear fiscal por defecto")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar cambios y no hacer commit")
    args = parser.parse_args()

    if args.pilot and args.no_pilot:
        print("No uses --pilot y --no-pilot a la vez.", file=sys.stderr)
        return 2

    user_patch: Dict[str, Any] = {}
    company_patch: Dict[str, Any] = {}
    owner_patch: Dict[str, Any] = {}

    if args.json_path:
        blob = _load_json(args.json_path)
        user_patch.update(blob.get("user") or {})
        company_patch.update(blob.get("company") or {})
        owner_patch.update(blob.get("owner_employee") or {})
        r = blob.get("remediate")
        if isinstance(r, dict):
            if r.get("business_type"):
                args.business_type = str(r["business_type"])
            if r.get("set_pilot") is True:
                args.pilot = True
            if r.get("set_pilot") is False:
                args.no_pilot = True

    if args.full_name is not None:
        user_patch["full_name"] = args.full_name
    if args.phone is not None:
        user_patch["phone"] = args.phone
    if args.company_name is not None:
        company_patch["company_name"] = args.company_name
    if args.sector is not None:
        company_patch["sector"] = args.sector
    if args.pilot:
        company_patch["pilot_company"] = True
    if args.no_pilot:
        company_patch["pilot_company"] = False
    if args.owner_name is not None:
        owner_patch["full_name"] = args.owner_name
    if args.owner_phone is not None:
        owner_patch["phone"] = args.owner_phone
    if args.owner_role is not None:
        owner_patch["role_title"] = args.owner_role

    from app.db.session import SessionLocal
    from app.models.company import Company, UserCompany
    from app.models.company_employee import CompanyEmployee
    from app.models.user import User
    from services.onboarding_engine import remediate_existing_company

    db = SessionLocal()
    report: Dict[str, Any] = {"company_id": args.company_id, "applied": []}

    try:
        company = db.query(Company).filter(Company.id == args.company_id).first()
        if not company:
            print(f"Empresa id={args.company_id} no existe.", file=sys.stderr)
            return 1

        if args.remediate:
            rem = remediate_existing_company(
                db,
                args.company_id,
                business_type=args.business_type,
                set_pilot_flag=bool(company_patch.get("pilot_company")) if company_patch.get("pilot_company") is not None else args.pilot,
                seed_fiscal=not args.no_fiscal_seed,
                commit=not args.dry_run,
            )
            report["remediate"] = rem
            if not rem.get("success"):
                print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
                return 1
            db.refresh(company)

        uid = args.user_id
        if uid is None:
            link = (
                db.query(UserCompany)
                .filter(UserCompany.company_id == args.company_id)
                .order_by(UserCompany.id.asc())
                .first()
            )
            if not link:
                print("Sin user_companies para esta empresa; pasa --user-id.", file=sys.stderr)
                return 1
            uid = link.user_id

        user = db.query(User).filter(User.id == uid).first()
        if not user:
            print(f"Usuario id={uid} no existe.", file=sys.stderr)
            return 1

        if user_patch:
            if "full_name" in user_patch and user_patch["full_name"] is not None:
                user.full_name = str(user_patch["full_name"]).strip()[:255] or None
                report["applied"].append("user.full_name")
            if "phone" in user_patch and user_patch["phone"] is not None:
                user.phone = str(user_patch["phone"]).strip()[:32] or None
                report["applied"].append("user.phone")
            db.add(user)

        allowed_co = {"company_name", "sector", "pilot_company", "country", "currency"}
        for k, v in company_patch.items():
            if k not in allowed_co or v is None:
                continue
            if k == "company_name":
                company.company_name = str(v).strip()[:255]
                user.company_name = company.company_name[:255]
                db.add(user)
                report["applied"].append("company.company_name (+ user.company_name)")
            elif k == "sector":
                company.sector = str(v).strip()[:100] or None
                report["applied"].append("company.sector")
            elif k == "pilot_company":
                company.pilot_company = bool(v)
                report["applied"].append("company.pilot_company")
            elif k == "country":
                company.country = str(v).strip()[:10] or None
                report["applied"].append("company.country")
            elif k == "currency":
                company.currency = str(v).strip()[:10] or "EUR"
                report["applied"].append("company.currency")
        db.add(company)

        owner_code = f"U{user.id}-OWNER"
        emp = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id == args.company_id,
                CompanyEmployee.employee_code == owner_code,
            )
            .first()
        )
        if not emp:
            emp = (
                db.query(CompanyEmployee)
                .filter(
                    CompanyEmployee.company_id == args.company_id,
                    CompanyEmployee.user_id == user.id,
                )
                .first()
            )
        if emp and owner_patch:
            if "full_name" in owner_patch and owner_patch["full_name"] is not None:
                emp.full_name = str(owner_patch["full_name"]).strip()[:255]
                report["applied"].append("company_employees.full_name (titular)")
            if "phone" in owner_patch and owner_patch["phone"] is not None:
                emp.phone = str(owner_patch["phone"]).strip()[:32] or None
                report["applied"].append("company_employees.phone (titular)")
            if "role_title" in owner_patch and owner_patch["role_title"] is not None:
                emp.role_title = str(owner_patch["role_title"]).strip()[:100] or None
                report["applied"].append("company_employees.role_title (titular)")
            db.add(emp)
        elif owner_patch and not emp:
            report["warning"] = (
                f"No hay fila titular ({owner_code}); ejecuta --remediate o audit --backfill-owner."
            )

        if args.dry_run:
            db.rollback()
            report["dry_run"] = True
        else:
            db.commit()
            report["committed"] = True

        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as e:
        db.rollback()
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
