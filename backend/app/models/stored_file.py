"""Registro de ficheros guardados en almacenamiento de objetos externo (Cloudflare R2).

Fase 2 / Step 1: ningun fichero subido vive en el disco local de Railway ni se sirve
por /static. El binario esta en R2 bajo `empresa/{company_id}/{categoria}/...`; esta
tabla es la unica fuente de verdad de a que empresa pertenece cada objeto, y todo
acceso pasa por /api/v1/files/{id} (THALOS + filtro de empresa + URL firmada corta).
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func

from app.db.base import Base


class StoredFile(Base):
    __tablename__ = "stored_files"

    # uuid4 hex: identificador no enumerable (no es la clave de acceso: el acceso exige
    # usuario autenticado de la misma empresa).
    id = Column(String(32), primary_key=True)
    company_id = Column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String(32), nullable=False, index=True)
    object_key = Column(String(512), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    # Ruta antigua bajo STATIC_DIR (p. ej. "uploads/images/u5_..._foto.png") de los ficheros
    # migrados desde disco: permite resolver las URLs /static/uploads/... ya guardadas en BD.
    legacy_path = Column(String(512), nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
