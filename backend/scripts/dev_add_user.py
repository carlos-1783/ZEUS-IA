"""
Crea un usuario en la base de datos configurada por DATABASE_URL (local o Railway)
si el email aún no existe. Útil para alinear usuarios de producción con SQLite local.

Uso (desde la carpeta backend, con el venv activado):
  python scripts/dev_add_user.py correo@ejemplo.com "Password1a" --full-name "Nombre" --phone 600123456

Empleado de una empresa ya creada (solo TPV + control horario en la app):
  python scripts/dev_add_user.py ana@empresa.com "Password1a" --full-name "Ana" --phone 662000000 \\
    --role employee --link-company-id 5 --employee-code CKR-ANA-01

La contraseña debe cumplir las mismas reglas que el registro (≥8, mayúscula, minúscula, número).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.company import Company, UserCompany  # noqa: F401 — mapper User.user_companies
from app.models.company_employee import CompanyEmployee
from app.models.user import User


def _slugify(value: str) -> str:
    s = (value or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "empresa"


def _ensure_default_company_local(db, user: User):
    """
    Misma lógica que ensure_user_company_link_for_operations pero sin importar
    global_company_bootstrap (evita cadena whatsapp_service + prints Unicode en consola Windows).
    """
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if link:
        return link.company_id

    role = (getattr(user, "role", None) or "owner").strip().lower()
    if role == "employee" and not getattr(user, "is_superuser", False):
        return None

    label = (
        (getattr(user, "company_name", None) or "").strip()
        or (getattr(user, "full_name", None) or "").strip()
        or (getattr(user, "email", None) or "").split("@")[0].strip()
        or "Mi negocio"
    )
    tail = _slugify(label)[:72]
    slug = f"u{user.id}-{tail}" if tail else f"u{user.id}"
    if len(slug) > 100:
        slug = slug[:100]

    company = Company(
        company_name=label[:255],
        slug=slug,
        pilot_company=False,
        status="active",
        sector=None,
        country="ES",
        currency="EUR",
        metadata_={
            "billing_enabled": False,
            "onboarding_completed": False,
            "source": "dev_add_user",
        },
    )
    db.add(company)
    db.flush()
    db.add(
        UserCompany(
            user_id=user.id,
            company_id=company.id,
            role="company_admin",
        )
    )
    db.commit()
    db.refresh(company)
    return company.id


def _password_ok(p: str) -> tuple[bool, str]:
    if len(p) < 8:
        return False, "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", p):
        return False, "Necesita una mayúscula"
    if not re.search(r"[a-z]", p):
        return False, "Necesita una minúscula"
    if not re.search(r"[0-9]", p):
        return False, "Necesita un número"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Añadir usuario a la BD actual (desarrollo)")
    parser.add_argument("email", help="Email (se normaliza a minúsculas)")
    parser.add_argument("password", help="Contraseña fuerte")
    parser.add_argument("--full-name", default="Usuario local", dest="full_name")
    parser.add_argument("--phone", default="600000000")
    parser.add_argument("--superuser", action="store_true", help="Marcar como superusuario")
    parser.add_argument(
        "--role",
        choices=("owner", "employee"),
        default="owner",
        help="owner = acceso completo; employee = solo TPV + control horario (front)",
    )
    parser.add_argument(
        "--link-company-id",
        type=int,
        default=None,
        dest="link_company_id",
        help="Vincular a esta empresa existente (no crea Company nueva). Típico con --role employee.",
    )
    parser.add_argument(
        "--employee-code",
        default=None,
        dest="employee_code",
        help="Con --link-company-id: asignar user_id en company_employees para este código (fichaje/TPV).",
    )
    args = parser.parse_args()

    ok, msg = _password_ok(args.password)
    if not ok:
        print(f"Contraseña inválida: {msg}")
        return 1

    email = args.email.strip().lower()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            try:
                cid = _ensure_default_company_local(db, existing)
                print(f"Ya existe: {email} (id={existing.id}) company_id={cid}")
            except Exception as e:
                print(f"Ya existe: {email} (id={existing.id}) empresa: {repr(e)}")
            return 0

        u = User(
            email=email,
            full_name=(args.full_name or "Usuario").strip()[:200],
            phone=(args.phone or "").strip()[:32] or None,
            hashed_password=get_password_hash(args.password),
            is_active=True,
            is_superuser=args.superuser,
            role=str(args.role).strip().lower() or "owner",
        )
        db.add(u)
        db.commit()
        db.refresh(u)

        if args.link_company_id is not None:
            co = db.query(Company).filter(Company.id == args.link_company_id).first()
            if not co:
                print(f"Empresa id={args.link_company_id} no existe.")
                return 1
            uc = (
                db.query(UserCompany)
                .filter(
                    UserCompany.user_id == u.id,
                    UserCompany.company_id == co.id,
                )
                .first()
            )
            if not uc:
                uc_role = "member" if u.role == "employee" else "company_admin"
                db.add(
                    UserCompany(
                        user_id=u.id,
                        company_id=co.id,
                        role=uc_role,
                    )
                )
                db.commit()
            else:
                uc_role = uc.role
            if co.company_name and not (u.company_name or "").strip():
                u.company_name = co.company_name[:255]
                db.add(u)
                db.commit()
            if args.employee_code:
                code = str(args.employee_code).strip()
                ce = (
                    db.query(CompanyEmployee)
                    .filter(
                        CompanyEmployee.company_id == co.id,
                        CompanyEmployee.employee_code == code,
                    )
                    .first()
                )
                if ce:
                    ce.user_id = u.id
                    db.add(ce)
                    db.commit()
                    print(f"OK company_employees.user_id para código {code}")
                else:
                    print(f"Aviso: no hay company_employees {code} en company_id={co.id}")
            print(f"OK vinculado user_id={u.id} a company_id={co.id} user_companies.role={uc_role}")
        else:
            try:
                cid = _ensure_default_company_local(db, u)
                print(f"OK empresa company_id={cid}")
            except Exception as e:
                print(f"Aviso empresa: {repr(e)}")

        print(f"OK creado user_id={u.id} email={email} superuser={args.superuser} role={u.role}")
        return 0
    except IntegrityError:
        db.rollback()
        print(f"Error integridad (email duplicado): {email}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
