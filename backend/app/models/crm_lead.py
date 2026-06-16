"""Leads CRM con scoring para zeus_final_closure_v2."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class CrmLead(Base):
    __tablename__ = "crm_leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(32), nullable=True)
    sector = Column(String(100), nullable=True)
    estimated_value = Column(Float, nullable=True, default=0.0)
    lead_score = Column(Float, nullable=True, default=0.0)
    customer_priority = Column(String(32), nullable=True)  # low|medium|high
    next_best_action = Column(String(128), nullable=True)
    meeting_at = Column(DateTime(timezone=True), nullable=True)
    converted_customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), nullable=False, default="open", index=True)  # open|converted|lost
    external_insights_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
