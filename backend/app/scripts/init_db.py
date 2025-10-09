import logging
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.append(project_root)

from app.core.config import settings
from app.db.base import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def init_db() -> None:
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if the superuser already exists
    user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER_EMAIL).first()
    if not user:
        # Create the first superuser
        user_in = {
            "email": settings.FIRST_SUPERUSER_EMAIL,
            "hashed_password": get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            "full_name": "Admin",
            "is_superuser": True,
        }
        db_user = User(**user_in)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logging.info("Superuser created")
    else:
        logging.info("Superuser already exists")
    
    db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Creating initial data")
    init_db()
    logger.info("Initial data created")
