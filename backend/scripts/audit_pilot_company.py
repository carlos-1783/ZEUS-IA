#!/usr/bin/env python3
"""
Auditoría de empresa piloto (ej. Circo Kanroka): qué hay y qué falta.

Uso (desde backend/, con venv y DATABASE_URL):
  python scripts/audit_pilot_company.py
  python scripts/audit_pilot_company.py --needle circo --needle kanroka

No modifica datos salvo que uses --backfill-owner (crea empleado titular + turnos).
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditar empresa piloto en BD")
    parser.add_argument(
        "--needle",
        action="append",
        default=[],
        help="Texto a buscar en nombre o slug (puede repetirse). Por defecto: circo, kanroka",
    )
    parser.add_argument(
        "--backfill-owner",
        action="store_true",
        help="Crear company_employee titular + turnos L-V si faltan (idempotente)",
    )
    args = parser.parse_args()
    needles = args.needle if args.needle else ["circo", "kanroka"]

    from sqlalchemy import or_

    from app.db.session import SessionLocal
    from app.models.company import Company, UserCompany
    from app.models.company_employee import CompanyEmployee
    from app.models.erp import TPVProduct, FiscalProfile, TaxRate
    from app.models.tpv_table import TPVTable
    from app.models.user import User

    db = SessionLocal()
    try:
        conds = []
        for n in needles:
            s = (n or "").strip()
            if not s:
                continue
            like = f"%{s}%"
            conds.append(Company.company_name.ilike(like))
            conds.append(Company.slug.ilike(like))
        if not conds:
            print("Sin criterios de búsqueda.")
            return 1

        rows = db.query(Company).filter(or_(*conds)).order_by(Company.id.asc()).all()
        # Un solo bloque por empresa aunque varios --needle coincidan
        companies = list({x.id: x for x in rows}.values())
        companies.sort(key=lambda x: x.id)
        if not companies:
            print(f"No se encontró ninguna empresa con: {needles}")
            print("Sugerencia: revisa slug/nombre en la tabla companies o amplía --needle.")
            return 2

        for c in companies:
            print("\n" + "=" * 72)
            print(f"EMPRESA id={c.id} name={c.company_name!r} slug={c.slug!r}")
            print(f"  pilot_company={c.pilot_company} status={c.status} sector={c.sector}")
            meta = c.metadata_ if isinstance(c.metadata_, dict) else {}
            print(f"  metadata keys: {list(meta.keys())[:20]}{'...' if len(meta) > 20 else ''}")

            links = db.query(UserCompany).filter(UserCompany.company_id == c.id).all()
            print(f"  user_companies: {len(links)} vínculo(s)")
            user_ids = [x.user_id for x in links]
            for uc in links:
                u = db.query(User).filter(User.id == uc.user_id).first()
                em = u.email if u else "?"
                print(f"    - user_id={uc.user_id} email={em!r} role={uc.role}")

            emp_rows = []
            try:
                emp_rows = (
                    db.query(CompanyEmployee).filter(CompanyEmployee.company_id == c.id).all()
                )
            except Exception as ex:
                print(f"  company_employees: error ({ex}) — ejecuta alembic upgrade head")
            print(f"  company_employees: {len(emp_rows)}")
            for e in emp_rows[:10]:
                print(f"    - id={e.id} code={e.employee_code!r} name={e.full_name!r} user_id={e.user_id}")

            tables_n = db.query(TPVTable).filter(TPVTable.company_id == c.id).count()
            print(f"  tpv_tables: {tables_n}")

            products_by_company = 0
            products_legacy = 0
            if user_ids:
                try:
                    products_by_company = (
                        db.query(TPVProduct)
                        .filter(TPVProduct.company_id == c.id)
                        .count()
                    )
                    products_legacy = (
                        db.query(TPVProduct)
                        .filter(
                            TPVProduct.user_id.in_(user_ids),
                            TPVProduct.company_id.is_(None),
                        )
                        .count()
                    )
                except Exception:
                    products_legacy = (
                        db.query(TPVProduct)
                        .filter(TPVProduct.user_id.in_(user_ids))
                        .count()
                    )
            print(
                f"  tpv_products (company_id={c.id}): {products_by_company}; "
                f"legacy sin company_id para usuarios de la empresa: {products_legacy}"
            )

            # Perfil fiscal / tasas por primer usuario dueño
            if user_ids:
                uid0 = user_ids[0]
                fp = db.query(FiscalProfile).filter(FiscalProfile.user_id == uid0).first()
                tr = db.query(TaxRate).filter(TaxRate.user_id == uid0).count()
                print(f"  fiscal_profile (user {uid0}): {'sí' if fp else 'NO'}")
                print(f"  tax_rates (user {uid0}): {tr}")

            # employee_schedules (si existe tabla)
            from sqlalchemy import inspect

            bind = db.get_bind()
            insp = inspect(bind)
            if insp.has_table("employee_schedules"):
                from app.models.time_tracking import EmployeeSchedule

                codes = [e.employee_code for e in emp_rows]
                if codes:
                    sch_n = (
                        db.query(EmployeeSchedule)
                        .filter(EmployeeSchedule.employee_id.in_(codes))
                        .count()
                    )
                else:
                    sch_n = 0
                print(f"  employee_schedules (por codes de la empresa): {sch_n}")
            else:
                print("  employee_schedules: tabla NO existe (crear con create_all / migración)")

            # Qué falta (heurística)
            gaps = []
            if not links:
                gaps.append("Sin usuarios vinculados (user_companies)")
            if not emp_rows:
                gaps.append("Sin filas en company_employees (titular RRHH)")
            nm = (c.company_name or "").lower()
            sec = (c.sector or "").lower()
            looks_horeca = any(
                x in nm or x in sec
                for x in ("restaurant", "restaurante", "bar", "cafeter", "circo", "hosteler")
            )
            if tables_n == 0 and looks_horeca:
                gaps.append("Sin mesas TPV (negocio tipo hostelería probable sin tpv_tables)")
            if products_by_company == 0 and products_legacy == 0 and user_ids:
                gaps.append("Sin productos TPV para esta empresa / usuarios")
            if not c.pilot_company:
                gaps.append("pilot_company=False (marcar en BD si debe ser piloto oficial)")
            if gaps:
                print("  >>> FALTA / REVISAR:")
                for g in gaps:
                    print(f"      - {g}")
            else:
                print("  >>> Comprobaciones básicas OK (revisa negocio a mano).")

            if args.backfill_owner:
                from services.onboarding_engine import ensure_company_owner_employee_and_shifts

                r = ensure_company_owner_employee_and_shifts(db, c.id)
                print(f"  --backfill-owner => {r}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
