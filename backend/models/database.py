"""
ZEUS-IA - Database Configuration
Configuración de SQLAlchemy y sesiones
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config.settings import get_settings

settings = get_settings()

# Motor de base de datos
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,  # True para debug SQL
)

# Sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()


def get_db():
    """
    Dependency para obtener sesión de DB
    Uso en FastAPI:
    
    @app.get("/users")
    def get_users(db: Session = Depends(get_db)):
        return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Inicializa la base de datos
    Crea todas las tablas si no existen
    """
    from backend.models import (
        User,
        Decision,
        AuditLog,
        Metric,
        HITLQueue,
    )
    
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada")


def reset_db():
    """
    ⚠️ PELIGRO: Borra toda la base de datos
    Solo usar en desarrollo
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("🔄 Base de datos reiniciada")

