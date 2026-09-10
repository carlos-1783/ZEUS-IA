"""Vertical Seguros — modelos reales (no simulados).

Primer trabajo de la vertical Seguros (AUDITORIA_100_COMPLETA.md: 0% de
código, ningún modelo de datos). Ciclo Multirriesgo: captación -> venta ->
gestión -> siniestros.

Decisiones de diseño:
- `coverages` (InsurancePolicy) y `insured_risk` (InsurancePolicy) son JSON
  libres a propósito: Multirriesgo hoy, otro ramo (Auto, Vida, Salud...)
  mañana, sin migración de esquema nueva. No se hardcodean columnas por
  tipo de cobertura.
- `status` se guarda con `values_callable` (valor en minúscula, no nombre),
  el mismo patrón que evita el bug de serialización Enum SQLAlchemy<->
  Pydantic ya documentado y corregido en el módulo ERP (CICLO_PRODUCCION.md,
  Ciclo 2) — aquí se evita desde el origen en vez de parchear después.
- `InsuranceClaim.company_id` duplica el dato ya presente en
  `InsurancePolicy.company_id` de forma intencional: así el RLS y los
  filtros de aplicación no dependen de un JOIN para aislar por tenant.
- `documents` (InsuranceClaim) es una lista de referencias (JSON) a
  ficheros ya subidos vía el endpoint real de subida unificada del
  proyecto (`POST /api/v1/upload`) — no se construye un sistema de storage
  nuevo.
- `branch` (piloto Mati/Catalana Occidente, feature/ramos-seguros-mati):
  enum real con los 6 ramos que gestiona Mati (hogar, comunidad, coche,
  vida, decesos, salud). Sin columna de aseguradora emisora: Mati es agente
  exclusiva de una sola compañía. Los campos específicos de Coche/Vida/Salud
  (matrícula, conductor habitual, marca/modelo; beneficiario, capital
  asegurado; nº asegurados, cuadro médico) se guardan dentro de
  `insured_risk` (ya JSON libre) en vez de columnas nuevas por ramo —
  Hogar/Comunidad/Decesos no necesitan campos adicionales.
"""

from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.db.base import Base


class PolicyStatus(PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PolicyBranch(PyEnum):
    """Ramo de la póliza. Piloto Mati (agente exclusiva Catalana Occidente,
    sin campo de aseguradora emisora): los 6 ramos que gestiona."""

    HOGAR = "hogar"
    COMUNIDAD = "comunidad"
    COCHE = "coche"
    VIDA = "vida"
    DECESOS = "decesos"
    SALUD = "salud"


class ClaimStatus(PyEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class InsurancePolicy(Base):
    """Póliza de seguro (ramo Multirriesgo y, a futuro, otros ramos)."""

    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, index=True)

    # Tenant — obligatorio, indexado (filtro de aplicación + RLS).
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)

    policy_number = Column(String(50), unique=True, index=True, nullable=False)

    # Ramo de la póliza (piloto Mati / Catalana Occidente): hogar, comunidad,
    # coche, vida, decesos, salud. Sin campo de aseguradora emisora — Mati es
    # agente exclusiva de una sola compañía.
    branch = Column(
        SAEnum(
            PolicyBranch,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            name="insurance_policy_branch",
        ),
        nullable=False,
        index=True,
    )

    # Estructura flexible: hoy Multirriesgo (cobertura_hogar, cobertura_incendio,
    # cobertura_robo, capitales asegurados...), mañana otro ramo, sin migración nueva.
    coverages = Column(JSON, nullable=False, default=dict)

    # Descripción del bien/riesgo asegurado y campos específicos por ramo
    # (dirección, m2, matrícula/conductor/marca-modelo en Coche, beneficiario/
    # capital asegurado en Vida, nº asegurados/cuadro médico en Salud...) —
    # JSON libre, mismo motivo que `coverages`: sin migración de esquema nueva
    # por cada ramo.
    insured_risk = Column(JSON, nullable=True, default=dict)

    premium_amount = Column(Numeric(10, 2), nullable=False)

    start_date = Column(Date, nullable=False, default=date.today)
    renewal_date = Column(Date, nullable=True)

    status = Column(
        SAEnum(
            PolicyStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            name="insurance_policy_status",
        ),
        nullable=False,
        default=PolicyStatus.DRAFT,
    )

    notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    claims = relationship(
        "InsuranceClaim",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="InsuranceClaim.id.desc()",
    )


class InsuranceClaim(Base):
    """Siniestro abierto sobre una póliza."""

    __tablename__ = "insurance_claims"

    id = Column(Integer, primary_key=True, index=True)

    policy_id = Column(Integer, ForeignKey("insurance_policies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Duplicado deliberado de InsurancePolicy.company_id: RLS y filtros de
    # aplicación no dependen de un JOIN para aislar por tenant.
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    claim_date = Column(Date, nullable=False, default=date.today)
    description = Column(Text, nullable=False)

    status = Column(
        SAEnum(
            ClaimStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            name="insurance_claim_status",
        ),
        nullable=False,
        default=ClaimStatus.OPEN,
    )

    estimated_amount = Column(Numeric(10, 2), nullable=True)
    resolved_amount = Column(Numeric(10, 2), nullable=True)

    # Lista de referencias a ficheros subidos vía POST /api/v1/upload:
    # [{"name": ..., "url": ..., "content_type": ..., "size_bytes": ..., "uploaded_at": ...}]
    documents = Column(JSON, nullable=False, default=list)

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    policy = relationship("InsurancePolicy", back_populates="claims")
