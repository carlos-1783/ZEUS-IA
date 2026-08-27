"""
Cierre del hallazgo "toolkit legal = stub" en la ruta de automatización
(teamflow_engine.py -> HANDLER_MAP["JUSTICIA"]["document_reviewed"/"compliance_check"]
-> handle_justicia_task).

Antes: `handle_justicia_task` devolvía SIEMPRE el mismo texto fijo de
política de privacidad / términos de servicio, sin leer ni escribir nada en
BD, con "docs_generated": 3 hardcodeado -- exactamente el patrón "toolkit
legal = stub" ya cerrado en POST /api/v1/justice/contracts/generate, pero
seguía vivo aquí. Ver AUDIT_JUSTICIA_ESTADO_FINAL.md.

Después: ejecuta GDPR real (`services.gdpr_engine.run_gdpr_check`) y lee
documentos pendientes reales (`services.justice_audit_service`) scopeados
al usuario real de la actividad; si el payload trae `document_id` también
intenta una firma real.
"""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.legal_document import LegalDocument
from app.models.user import User
from services.automation.handlers.justicia import handle_justicia_task


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_user(db: Session) -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"justicia_handler_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Justicia Handler Tester",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_activity(db: Session, *, action_type: str, user_email, details=None) -> AgentActivity:
    row = AgentActivity(
        agent_name="JUSTICIA",
        action_type=action_type,
        action_description="test automation handler",
        details=details or {},
        user_email=user_email,
        status="pending",
        priority="normal",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_handle_justicia_task_no_longer_returns_fixed_boilerplate(db: Session):
    """El bug original: contenido idéntico sin importar el usuario/actividad."""
    user = _seed_user(db)
    activity = _make_activity(db, action_type="compliance_check", user_email=user.email)

    result = handle_justicia_task(activity)

    assert result["status"] == "completed"
    automation = result["details_update"]["automation"]
    assert result["details_update"]["real_execution"] is True
    assert result["details_update"]["data_origin"] == "database"
    # Ya no debe existir el texto fijo histórico.
    assert "privacy_policy" not in automation
    assert "terms_of_service" not in automation
    # Debe reflejar de verdad el estado en BD (sin documentos aun -> 0 pendientes).
    assert automation["pending_documents"]["total_pending"] == 0
    assert "gdpr_issues" in automation


def test_handle_justicia_task_reflects_real_pending_documents(db: Session):
    """Si el usuario tiene un documento draft real, el handler debe verlo -- no
    un número fijo como el "docs_generated": 3 histórico."""
    user = _seed_user(db)
    doc = LegalDocument(
        user_id=user.id,
        doc_type="contract",
        content="contenido real de prueba",
        status="draft",
        owner_agent="JUSTICIA",
        version=1,
    )
    db.add(doc)
    db.commit()

    activity = _make_activity(db, action_type="document_reviewed", user_email=user.email)
    result = handle_justicia_task(activity)

    assert result["status"] == "completed"
    pending = result["details_update"]["automation"]["pending_documents"]
    assert pending["legal_documents_draft"] == 1
    assert result["metrics_update"]["pending_documents_total"] == pending["total_pending"]


def test_handle_justicia_task_fails_honestly_without_user(db: Session):
    """Sin usuario resoluble, debe fallar explícito -- nunca simular éxito."""
    activity = _make_activity(db, action_type="task_assigned", user_email="no-existe@example.test")
    result = handle_justicia_task(activity)

    assert result["status"] == "failed"
    assert result["details_update"]["real_execution"] is False
    assert "error" in result["details_update"]


def test_handle_justicia_task_signs_real_document_when_document_id_present(db: Session):
    user = _seed_user(db)
    doc = LegalDocument(
        user_id=user.id,
        doc_type="contract",
        content="contenido a firmar",
        status="draft",
        owner_agent="JUSTICIA",
        version=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    activity = _make_activity(
        db,
        action_type="document_signed_via_task",
        user_email=user.email,
        details={"payload": {"document_id": doc.public_id}},
    )
    result = handle_justicia_task(activity)

    assert result["status"] == "completed"
    signature = result["details_update"]["automation"]["signature"]
    assert signature is not None
    assert signature["document_id"] == doc.public_id
    assert result["metrics_update"]["documents_signed"] == 1

    db.refresh(doc)
    assert doc.status == "approved"
    assert doc.signature_hash is not None


def test_handle_justicia_task_reports_signature_error_without_crashing(db: Session):
    user = _seed_user(db)
    activity = _make_activity(
        db,
        action_type="compliance_check",
        user_email=user.email,
        details={"payload": {"document_id": "no-existe-id"}},
    )
    result = handle_justicia_task(activity)

    assert result["status"] == "completed"
    automation = result["details_update"]["automation"]
    assert automation["signature"] is None
    assert automation["signature_error"]
