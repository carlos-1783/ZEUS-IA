"""
Seed de empresas de ejemplo (bar, zapatería) para probar distintos TPV e inicio
antes de la empresa piloto. Solo para uso local; no modifica lógica ni producción.

Uso (en local):
  cd backend
  set CONFIRM_SEED_DEMO=1
  python scripts/seed_demo_empresas.py

Credenciales creadas (misma contraseña para ambos):
  - Bar:      bar@demo.local      / Demo123!
  - Zapatería: zapateria@demo.local / Demo123!
"""
import os
import sys
from pathlib import Path

# Añadir backend al path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

# Seguridad: no ejecutar en Railway/producción salvo que se confirme explícitamente
if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"):
    if os.getenv("CONFIRM_SEED_DEMO") != "1":
        print("[SEED] No se ejecuta en Railway. Para forzar: CONFIRM_SEED_DEMO=1")
        sys.exit(0)

from app.db.session import SessionLocal
from app.models.user import User
from app.models.company import Company, UserCompany  # necesario para que el mapper de User resuelva user_companies
from app.models.erp import TPVProduct
from app.core.security import get_password_hash, verify_password

def _hash_password(password: str) -> str:
    """Hash que debe verificar verify_password de la API. Usamos passlib (mismo que la API)."""
    return get_password_hash(password)

# Contraseña común para ambos usuarios demo
DEMO_PASSWORD = "Demo123!"

# Productos de ejemplo para el bar (categorías del perfil bar)
PRODUCTOS_BAR = [
    ("Cerveza", "Bebidas", 2.50, "food"),
    ("Copa vino", "Bebidas Alcohólicas", 3.00, "food"),
    ("Refresco", "Bebidas", 2.00, "food"),
    ("Café", "Bebidas", 1.50, "food"),
    ("Agua", "Bebidas", 1.20, "food"),
    ("Tapa del día", "Tapas", 3.50, "food"),
    ("Bocadillo", "Tapas", 4.50, "food"),
    ("Ración patatas", "Raciones", 5.00, "food"),
    ("Ración jamón", "Raciones", 8.00, "food"),
]

EMPRESAS_EJEMPLO = [
    {
        "email": "bar@demo.local",
        "full_name": "Bar La Esquina",
        "company_name": "Bar La Esquina",
        "tpv_business_profile": "bar",
        "control_horario_business_profile": "restaurante",
    },
    {
        "email": "zapateria@demo.local",
        "full_name": "Zapatería Central",
        "company_name": "Zapatería Central",
        "tpv_business_profile": "tienda_minorista",
        "control_horario_business_profile": "tienda",
    },
]


def _inicializar_tpv_bar(db, user_id: int):
    """Crea productos de ejemplo en TPV para el usuario bar (solo si no tiene ninguno)."""
    from datetime import datetime
    n = db.query(TPVProduct).filter(TPVProduct.user_id == user_id).count()
    if n > 0:
        print(f"  TPV bar ya tiene {n} productos, no se añaden más.")
        return
    base_id = int(datetime.utcnow().timestamp() * 1000)
    for i, (name, category, price, icon) in enumerate(PRODUCTOS_BAR):
        product_id = f"PROD_{base_id}_{i:04d}"
        price_with_iva = round(price * 1.21, 2)
        db.add(TPVProduct(
            user_id=user_id,
            product_id=product_id,
            name=name,
            category=category,
            price=price,
            price_with_iva=price_with_iva,
            iva_rate=21.0,
            stock=None,
            image=None,
            icon=icon,
            metadata_={},
        ))
    db.commit()
    print(f"  TPV bar inicializado: {len(PRODUCTOS_BAR)} productos de ejemplo.")


def main():
    if os.getenv("CONFIRM_SEED_DEMO") != "1":
        print("[SEED] Ejecutar solo en local con: set CONFIRM_SEED_DEMO=1")
        print("       Luego: python scripts/seed_demo_empresas.py")
        sys.exit(1)

    db = SessionLocal()
    try:
        for data in EMPRESAS_EJEMPLO:
            user = db.query(User).filter(User.email == data["email"]).first()
            if user:
                print(f"  Ya existe: {data['email']} ({data['company_name']})")
                continue
            user = User(
                email=data["email"],
                hashed_password=_hash_password(DEMO_PASSWORD),
                full_name=data["full_name"],
                is_active=True,
                is_superuser=False,
                role="owner",
                company_name=data["company_name"],
                plan="startup",
            )
            db.add(user)
            db.flush()
            if hasattr(User, "tpv_business_profile"):
                user.tpv_business_profile = data["tpv_business_profile"]
            if hasattr(User, "control_horario_business_profile"):
                user.control_horario_business_profile = data["control_horario_business_profile"]
            db.commit()
            print(f"  Creado: {data['email']} -> TPV {data['tpv_business_profile']}")

        # Asegurar que la contraseña de los demo verifique con la API (mismo verify_password)
        for data in EMPRESAS_EJEMPLO:
            u = db.query(User).filter(User.email == data["email"]).first()
            if not u:
                continue
            # Probar si la contraseña actual ya verifica
            if verify_password(DEMO_PASSWORD, u.hashed_password):
                print(f"  OK contraseña ya válida: {data['email']}")
                continue
            # Intentar con passlib (mismo que la API)
            u.hashed_password = get_password_hash(DEMO_PASSWORD)
            db.commit()
            db.refresh(u)
            if verify_password(DEMO_PASSWORD, u.hashed_password):
                print(f"  Contraseña actualizada (passlib): {data['email']}")
                continue
            # Fallback: bcrypt directo (passlib.verify acepta hashes bcrypt estándar)
            try:
                import bcrypt
                u.hashed_password = bcrypt.hashpw(DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                db.commit()
                db.refresh(u)
                if verify_password(DEMO_PASSWORD, u.hashed_password):
                    print(f"  Contraseña actualizada (bcrypt): {data['email']}")
                else:
                    print(f"  AVISO: {data['email']} - verifica manualmente el login")
            except Exception as e:
                print(f"  Error bcrypt para {data['email']}: {e}")

        # Inicializar TPV del bar: productos de ejemplo para bar@demo.local
        bar_user = db.query(User).filter(User.email == "bar@demo.local").first()
        if bar_user:
            _inicializar_tpv_bar(db, bar_user.id)

        print("\nCredenciales (contraseña para ambos):", DEMO_PASSWORD)
        print("Puedes iniciar sesión en la app con bar@demo.local o zapateria@demo.local")
        print("para ver el TPV e inicio según tipo de negocio (sin afectar empresa piloto).")
    except Exception as e:
        db.rollback()
        print("[SEED] Error:", e)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
