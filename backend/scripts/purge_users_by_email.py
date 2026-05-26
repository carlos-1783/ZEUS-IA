"""
Elimina usuarios (y sus empresas exclusivas) por email sin afectar al resto del tenant.

Uso:
  cd backend
  python scripts/purge_users_by_email.py --dry-run
  python scripts/purge_users_by_email.py --execute

Requiere DATABASE_URL o SQLALCHEMY_DATABASE_URI en el entorno.
"""

from __future__ import annotations

import argparse
import os
import sys

# Asegurar imports desde backend/
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User, RefreshToken, PasswordResetToken
from app.models.company import Company, UserCompany
from app.models.agent_activity import AgentActivity
from app.models.document_approval import DocumentApproval
from app.models.customer import Customer, ContactPerson
from app.models.erp import TPVSale, TPVSaleItem, TPVProduct
from app.models.chat_message import ChatMessage
from app.models.time_tracking import (
    TimeTrackingRecord,
    EmployeeSchedule,
    TimeControlEvent,
    TimeControlAlert,
    AttendanceReport,
)
from app.models.automation_readiness import AutomationReadiness

DEFAULT_EMAILS = (
    "equipo@wwwavefenix.com",
    "fenixa944@gmail.com",
    "test_verificacion_123@test.com",
)


def _norm(email: str) -> str:
    return (email or "").strip().lower()


def find_users(db: Session, emails: list[str]) -> list[User]:
    found: list[User] = []
    for raw in emails:
        e = _norm(raw)
        u = db.query(User).filter(func.lower(User.email) == e).first()
        if u:
            found.append(u)
        else:
            print(f"  [skip] No existe usuario: {raw}")
    return found


def company_ids_for_user(db: Session, user_id: int) -> list[int]:
    rows = (
        db.query(UserCompany.company_id)
        .filter(UserCompany.user_id == user_id)
        .all()
    )
    return [r[0] for r in rows]


def companies_exclusive_to_users(db: Session, user_ids: set[int]) -> list[int]:
    """Empresas cuyos vínculos pertenecen SOLO a los usuarios indicados."""
    exclusive: list[int] = []
    if not user_ids:
        return exclusive
    all_cids = set()
    for uid in user_ids:
        all_cids.update(company_ids_for_user(db, uid))
    for cid in all_cids:
        links = db.query(UserCompany).filter(UserCompany.company_id == cid).all()
        link_user_ids = {l.user_id for l in links}
        if link_user_ids and link_user_ids <= user_ids:
            exclusive.append(cid)
    return exclusive


def purge_user_scoped_rows(db: Session, user: User, dry_run: bool) -> dict:
    uid = user.id
    email = user.email
    counts: dict[str, int] = {}

    def _del(label: str, n: int):
        counts[label] = counts.get(label, 0) + n

    # Actividades por email
    n = db.query(AgentActivity).filter(AgentActivity.user_email == email).count()
    if n and not dry_run:
        db.query(AgentActivity).filter(AgentActivity.user_email == email).delete(
            synchronize_session=False
        )
    _del("agent_activities", n)

    # Documentos
    n = db.query(DocumentApproval).filter(DocumentApproval.user_id == uid).count()
    if n and not dry_run:
        db.query(DocumentApproval).filter(DocumentApproval.user_id == uid).delete(
            synchronize_session=False
        )
    _del("document_approvals", n)

    # TPV ventas + líneas
    sale_ids = [r[0] for r in db.query(TPVSale.id).filter(TPVSale.user_id == uid).all()]
    if sale_ids and not dry_run:
        db.query(TPVSaleItem).filter(TPVSaleItem.tpv_sale_id.in_(sale_ids)).delete(
            synchronize_session=False
        )
        db.query(TPVSale).filter(TPVSale.user_id == uid).delete(synchronize_session=False)
    _del("tpv_sales", len(sale_ids))

    n = db.query(TPVProduct).filter(TPVProduct.user_id == uid).count()
    if n and not dry_run:
        db.query(TPVProduct).filter(TPVProduct.user_id == uid).delete(synchronize_session=False)
    _del("tpv_products", n)

    # Clientes donde es owner (además de cascade por company)
    cust_ids = [
        r[0] for r in db.query(Customer.id).filter(Customer.owner_user_id == uid).all()
    ]
    if cust_ids and not dry_run:
        db.query(ContactPerson).filter(ContactPerson.customer_id.in_(cust_ids)).delete(
            synchronize_session=False
        )
        db.query(Customer).filter(Customer.id.in_(cust_ids)).delete(synchronize_session=False)
    _del("customers_owner", len(cust_ids))

    # Control horario
    for model, label in (
        (TimeTrackingRecord, "time_tracking_records"),
        (EmployeeSchedule, "employee_schedules"),
        (TimeControlEvent, "time_control_events"),
        (TimeControlAlert, "time_control_alerts"),
        (AttendanceReport, "attendance_reports"),
    ):
        n = db.query(model).filter(model.user_id == uid).count()
        if n and not dry_run:
            db.query(model).filter(model.user_id == uid).delete(synchronize_session=False)
        _del(label, n)

    # automation_readiness usa company_id -> users.id (legacy)
    n = db.query(AutomationReadiness).filter(AutomationReadiness.company_id == uid).count()
    if n and not dry_run:
        db.query(AutomationReadiness).filter(AutomationReadiness.company_id == uid).delete(
            synchronize_session=False
        )
    _del("automation_readiness", n)

    # Tokens (sin CASCADE en BD antigua)
    n = db.query(RefreshToken).filter(RefreshToken.user_id == uid).count()
    if n and not dry_run:
        db.query(RefreshToken).filter(RefreshToken.user_id == uid).delete(synchronize_session=False)
    _del("refresh_tokens", n)

    n = db.query(PasswordResetToken).filter(PasswordResetToken.email == email).count()
    if n and not dry_run:
        db.query(PasswordResetToken).filter(PasswordResetToken.email == email).delete(
            synchronize_session=False
        )
    _del("password_reset_tokens", n)

    # Chat (CASCADE en modelo; por si acaso)
    n = db.query(ChatMessage).filter(ChatMessage.user_id == uid).count()
    if n and not dry_run:
        db.query(ChatMessage).filter(ChatMessage.user_id == uid).delete(synchronize_session=False)
    _del("chat_messages", n)

    return counts


def purge_companies(db: Session, company_ids: list[int], dry_run: bool) -> int:
    if not company_ids:
        return 0
    if dry_run:
        return len(company_ids)
    for cid in company_ids:
        co = db.query(Company).filter(Company.id == cid).first()
        if co:
            db.delete(co)
    return len(company_ids)


def purge_users(db: Session, users: list[User], dry_run: bool) -> int:
    n = 0
    for u in users:
        if dry_run:
            n += 1
            continue
        db.delete(u)
        n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="Purgar usuarios ZEUS por email")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar borrado (sin esto solo informa)",
    )
    parser.add_argument(
        "--email",
        action="append",
        dest="emails",
        help="Email adicional (repetible)",
    )
    args = parser.parse_args()
    dry_run = not args.execute
    emails = list(args.emails) if args.emails else list(DEFAULT_EMAILS)
    emails = [_norm(e) for e in emails if e]

    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if not url:
        print("ERROR: Define DATABASE_URL o SQLALCHEMY_DATABASE_URI")
        return 1

    print("Modo:", "DRY-RUN (sin cambios)" if dry_run else "EJECUCIÓN REAL")
    print("Emails objetivo:", ", ".join(emails))
    print("BD:", url.split("@")[-1] if "@" in url else "(configurada)")

    db = SessionLocal()
    try:
        users = find_users(db, emails)
        if not users:
            print("No hay usuarios que borrar.")
            return 0

        user_ids = {u.id for u in users}
        print("\n--- Usuarios encontrados ---")
        for u in users:
            cids = company_ids_for_user(db, u.id)
            print(
                f"  id={u.id} email={u.email} "
                f"company_name={u.company_name!r} companies={cids} superuser={u.is_superuser}"
            )
            if u.is_superuser:
                print("  ERROR: es superusuario — NO se borrará por seguridad")
                return 2

        users = [u for u in users if not u.is_superuser]
        user_ids = {u.id for u in users}

        exclusive_companies = companies_exclusive_to_users(db, user_ids)
        print("\n--- Empresas a eliminar (solo vinculadas a estos usuarios) ---")
        for cid in exclusive_companies:
            co = db.query(Company).filter(Company.id == cid).first()
            print(f"  id={cid} slug={getattr(co, 'slug', '?')} name={getattr(co, 'company_name', '?')}")

        # Empresas compartidas con otros usuarios: no se borran la company
        shared = set()
        for uid in user_ids:
            for cid in company_ids_for_user(db, uid):
                if cid not in exclusive_companies:
                    shared.add(cid)
        if shared:
            print("\n--- Empresas NO borradas (otros usuarios vinculados) ---")
            for cid in shared:
                co = db.query(Company).filter(Company.id == cid).first()
                others = (
                    db.query(UserCompany.user_id)
                    .filter(UserCompany.company_id == cid)
                    .all()
                )
                print(f"  id={cid} slug={co.slug} otros_user_ids={[o[0] for o in others]}")

        total_counts: dict[str, int] = {}
        for u in users:
            print(f"\n--- Datos de user_id={u.id} ({u.email}) ---")
            c = purge_user_scoped_rows(db, u, dry_run)
            for k, v in c.items():
                total_counts[k] = total_counts.get(k, 0) + v
                if v:
                    print(f"  {k}: {v}")

        nc = purge_companies(db, exclusive_companies, dry_run)
        print(f"\ncompanies_deleted: {nc}")
        nu = purge_users(db, users, dry_run)
        print(f"users_deleted: {nu}")

        if dry_run:
            print("\n[DRY-RUN] Repite con --execute para aplicar.")
            db.rollback()
        else:
            db.commit()
            print("\nOK: cambios confirmados en BD.")
            # Verificación
            for e in emails:
                left = db.query(User).filter(func.lower(User.email) == e).first()
                print(f"  verificación {e}: {'ELIMINADO' if not left else 'AÚN EXISTE'}")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
