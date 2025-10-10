import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

from app.db.base import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def init_db():
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if admin user already exists
    admin_email = "admin@example.com"
    admin_user = db.query(User).filter(User.email == admin_email).first()
    
    if not admin_user:
        print("Creating admin user...")
        # Create admin user
        admin_user = User(
            email=admin_email,
            full_name="Admin User",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True
        )
        db.add(admin_user)
        db.commit()
        print(f"Admin user created with email: {admin_email} and password: admin123")
    else:
        print("Admin user already exists")
    
    db.close()
    print("Database initialization complete!")

if __name__ == "__main__":
    init_db()
