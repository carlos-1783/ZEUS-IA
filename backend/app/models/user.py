from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Legal-Fiscal Firewall fields
    email_gestor_fiscal = Column(String, nullable=True)
    email_asesor_legal = Column(String, nullable=True)
    autoriza_envio_documentos_a_asesores = Column(Boolean(), default=False)
    
    # Company info
    company_name = Column(String, nullable=True)
    employees = Column(Integer, nullable=True)
    plan = Column(String, nullable=True)  # startup, growth, business, enterprise

    def __repr__(self):
        return f"<User {self.email}>"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean(), default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="refresh_tokens")
    
    def __repr__(self):
        return f"<RefreshToken {self.token}>"


# Add relationships to User model
User.refresh_tokens = relationship("RefreshToken", order_by=RefreshToken.id, back_populates="user")
# Document approvals relationship (lazy import to avoid circular dependency)
User.document_approvals = relationship("DocumentApproval", order_by="DocumentApproval.created_at.desc()", back_populates="user")
