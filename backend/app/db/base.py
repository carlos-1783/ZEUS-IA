from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
) if "sqlite" in settings.DATABASE_URL else create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_tables():
    """Crear todas las tablas en la base de datos"""
    try:
        print("[DATABASE] Creando tablas...")
        # Importar modelos aquí para evitar importación circular
        from app.models.user import User, RefreshToken
        from app.models.customer import Customer
        from app.models.erp import Invoice, Product, Payment
        from app.models.agent_activity import AgentActivity
        
        Base.metadata.create_all(bind=engine)
        print("[DATABASE] ✅ Tablas creadas correctamente")
    except Exception as e:
        print(f"[DATABASE] ❌ Error al crear tablas: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
