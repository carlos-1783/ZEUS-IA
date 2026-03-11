"""Reservas web + TPV: multi-tenant por user_id (dueño del negocio)."""
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    guest_name = Column(String(200), nullable=False)
    guest_phone = Column(String(50), nullable=False)
    guest_email = Column(String(255), nullable=True)
    reservation_date = Column(Date(), nullable=False, index=True)
    reservation_time = Column(String(20), nullable=False)  # "20:00", "14:30"
    num_guests = Column(Integer, nullable=False)
    notes = Column(String(500), nullable=True)

    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | confirmed | cancelled | no_show | seated
    table_id = Column(String(50), nullable=True)
    table_name = Column(String(100), nullable=True)

    source = Column(String(20), nullable=False, default="web")  # web | manual
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="reservations")

    def __repr__(self):
        return f"<Reservation {self.id} {self.guest_name} {self.reservation_date} {self.reservation_time}>"
