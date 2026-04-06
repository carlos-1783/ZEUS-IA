#!/usr/bin/env python3
"""
Repara una empresa existente: sector, TPV profile, empleado titular, turnos,
productos/mesas si faltan, fiscal por defecto, metadata RPA.

Uso (desde backend/, venv y DATABASE_URL):
  python scripts/remediate_company_stack.py --company-id 2
  python scripts/remediate_company_stack.py --company-id 2 --pilot --type restaurant

Requiere migraciones al día (company_employees, employee_schedules, etc.).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    parser = argparse.ArgumentParser(description="Remediar empresa en BD (onboarding completo)")
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Marcar company.pilot_company=True",
    )
    parser.add_argument(
        "--type",
        dest="business_type",
        default="restaurant",
        help="business_type (default: restaurant)",
    )
    parser.add_argument(
        "--no-fiscal",
        action="store_true",
        help="No crear FiscalProfile / TaxRate por defecto",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Solo flush, sin commit (para depurar)",
    )
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from services.onboarding_engine import remediate_existing_company

    db = SessionLocal()
    try:
        result = remediate_existing_company(
            db,
            args.company_id,
            business_type=args.business_type,
            set_pilot_flag=args.pilot,
            seed_fiscal=not args.no_fiscal,
            commit=not args.no_commit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result.get("success") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
