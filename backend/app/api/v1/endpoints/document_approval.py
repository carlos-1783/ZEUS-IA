"""
🛡️ Document Approval Endpoints
Endpoints para aprobación de documentos generados por RAFAEL y JUSTICIA
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from services.legal_fiscal_firewall import firewall

router = APIRouter()


class ApprovalRequest(BaseModel):
    document_id: str
    agent_name: str  # "RAFAEL" or "JUSTICIA"
    document_content: Dict[str, Any]
    advisor_email: Optional[EmailStr] = None  # Opcional, si no se proporciona se usa el del usuario


class ApprovalResponse(BaseModel):
    success: bool
    message: str
    approval_record: Optional[Dict[str, Any]] = None
    send_result: Optional[Dict[str, Any]] = None


@router.post("/approve", response_model=ApprovalResponse)
async def approve_document(
    request: ApprovalRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Aprobar documento generado por RAFAEL o JUSTICIA y enviarlo al asesor.
    
    Requiere aprobación explícita del cliente antes de enviarse al asesor indicado.
    """
    try:
        # Verificar que el usuario tiene autorización para enviar documentos
        if not current_user.autoriza_envio_documentos_a_asesores:
            raise HTTPException(
                status_code=403,
                detail="No tienes autorización para enviar documentos a asesores. Por favor, configura esta autorización en tu perfil."
            )
        
        # Verificar que el agente es válido
        if request.agent_name not in ["RAFAEL", "JUSTICIA"]:
            raise HTTPException(
                status_code=400,
                detail="Agent name debe ser 'RAFAEL' o 'JUSTICIA'"
            )
        
        # Obtener documento de BD si existe
        from app.models.document_approval import DocumentApproval
        
        doc_approval = None
        if request.document_id:
            if isinstance(request.document_id, str) and request.document_id.isdigit():
                doc_approval = db.query(DocumentApproval).filter(
                    DocumentApproval.id == int(request.document_id),
                    DocumentApproval.user_id == current_user.id
                ).first()
            else:
                # Buscar por user_id y agent_name más reciente pendiente
                doc_approval = db.query(DocumentApproval).filter(
                    DocumentApproval.user_id == current_user.id,
                    DocumentApproval.agent_name == request.agent_name,
                    DocumentApproval.status.in_(["draft", "pending_approval"])
                ).order_by(DocumentApproval.created_at.desc()).first()
        
        # Si tenemos documento persistido, usar su contenido
        if doc_approval:
            document_content = doc_approval.document_payload.get("content", request.document_content)
            document_id = doc_approval.id
        else:
            document_content = request.document_content
            document_id = request.document_id
        
        # Configurar firewall con sesión de BD
        firewall.db = db
        
        # Aprobar y enviar al asesor
        result = await firewall.approve_and_send_to_advisor(
            user_id=current_user.id,
            document_id=str(document_id),
            user_email=current_user.email,
            agent_name=request.agent_name,
            document_content=document_content,
            advisor_email=request.advisor_email
        )
        
        if not result.get("success"):
            # Si falta email de asesor, retornar error específico
            if result.get("status") == "pending_advisor_email":
                return ApprovalResponse(
                    success=False,
                    message="Falta email de asesor. Proporcione un contacto para enviar.",
                    approval_record=result.get("approval_record")
                )
            
            # Error en el envío
            return ApprovalResponse(
                success=False,
                message=result.get("message", "Error al enviar documento al asesor"),
                approval_record=result.get("approval_record"),
                send_result=result.get("send_result")
            )
        
        return ApprovalResponse(
            success=True,
            message="Documento aprobado y enviado al asesor exitosamente",
            approval_record=result.get("approval_record"),
            send_result=result.get("send_result")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al aprobar documento: {str(e)}"
        )


@router.get("/pending")
async def get_pending_documents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    agent_name: Optional[str] = None  # Filtrar por agente (RAFAEL, JUSTICIA)
):
    """
    Obtener lista de documentos pendientes de aprobación del usuario.
    Incluye documentos fiscales de TPV.
    """
    try:
        from app.models.document_approval import DocumentApproval
        from services.legal_fiscal_firewall import DocumentStatus
        
        # Consultar documentos pendientes del usuario
        query = db.query(DocumentApproval).filter(
            DocumentApproval.user_id == current_user.id,
            DocumentApproval.status.in_([
                DocumentStatus.DRAFT.value,
                DocumentStatus.PENDING_APPROVAL.value,
                DocumentStatus.PENDING_REVIEW.value
            ])
        )
        
        # Filtrar por agente si se especifica
        if agent_name:
            query = query.filter(DocumentApproval.agent_name == agent_name.upper())
        
        pending_docs = query.order_by(DocumentApproval.created_at.desc()).all()
        
        documents = [doc.to_dict() for doc in pending_docs]
        
        return {
            "success": True,
            "pending_documents": documents,
            "count": len(documents),
            "message": f"{len(documents)} documento(s) pendiente(s) de aprobación" if documents else "No hay documentos pendientes de aprobación"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo documentos pendientes: {str(e)}"
        )


@router.get("/history")
async def get_approval_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """
    Obtener historial de aprobaciones del usuario.
    """
    try:
        from app.models.document_approval import DocumentApproval
        
        # Consultar historial de documentos del usuario (todos los estados excepto draft)
        history_docs = db.query(DocumentApproval).filter(
            DocumentApproval.user_id == current_user.id,
            DocumentApproval.status != "draft"
        ).order_by(DocumentApproval.created_at.desc()).limit(limit).all()
        
        history = [doc.to_dict() for doc in history_docs]
        
        return {
            "success": True,
            "history": history,
            "count": len(history),
            "message": f"{len(history)} documento(s) en historial" if history else "No hay historial de aprobaciones disponible"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo historial: {str(e)}"
        )


@router.post("/update-advisor-emails")
async def update_advisor_emails(
    email_gestor_fiscal: Optional[EmailStr] = None,
    email_asesor_legal: Optional[EmailStr] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar emails de asesores del usuario.
    """
    try:
        if email_gestor_fiscal:
            current_user.email_gestor_fiscal = email_gestor_fiscal
        
        if email_asesor_legal:
            current_user.email_asesor_legal = email_asesor_legal
        
        db.commit()
        db.refresh(current_user)
        
        return {
            "success": True,
            "message": "Emails de asesores actualizados correctamente",
            "email_gestor_fiscal": current_user.email_gestor_fiscal,
            "email_asesor_legal": current_user.email_asesor_legal
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando emails de asesores: {str(e)}"
        )


@router.post("/toggle-authorization")
async def toggle_document_authorization(
    autoriza: bool,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Activar/desactivar autorización para envío de documentos a asesores.
    """
    try:
        current_user.autoriza_envio_documentos_a_asesores = autoriza
        db.commit()
        db.refresh(current_user)
        
        return {
            "success": True,
            "message": f"Autorización {'activada' if autoriza else 'desactivada'} correctamente",
            "autoriza_envio_documentos_a_asesores": current_user.autoriza_envio_documentos_a_asesores
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando autorización: {str(e)}"
        )


@router.post("/{document_id}/export")
async def export_fiscal_document(
    document_id: int,
    format: str = "json",  # json, xml, pdf
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Exportar documento fiscal en formato especificado (JSON, XML, PDF).
    Actualiza estado a 'exported' después de exportar.
    """
    try:
        from app.models.document_approval import DocumentApproval
        from services.legal_fiscal_firewall import DocumentStatus
        from datetime import datetime
        import json
        
        # Buscar documento del usuario
        doc_approval = db.query(DocumentApproval).filter(
            DocumentApproval.id == document_id,
            DocumentApproval.user_id == current_user.id,
            DocumentApproval.agent_name == "RAFAEL"
        ).first()
        
        if not doc_approval:
            raise HTTPException(
                status_code=404,
                detail="Documento fiscal no encontrado o no tienes permisos para acceder"
            )
        
        # Validar formato
        if format not in ["json", "xml", "pdf"]:
            raise HTTPException(
                status_code=400,
                detail="Formato inválido. Usa: json, xml, pdf"
            )
        
        # Obtener contenido del documento
        document_content = doc_approval.document_payload
        
        # Generar export según formato
        export_data = None
        content_type = None
        filename = None
        
        if format == "json":
            export_data = json.dumps(document_content, ensure_ascii=False, indent=2)
            content_type = "application/json"
            filename = f"fiscal_document_{document_id}.json"
        elif format == "xml":
            # Generar XML básico (estructura simplificada)
            from xml.etree.ElementTree import Element, tostring
            root = Element("FiscalDocument")
            root.set("id", str(document_id))
            root.set("type", doc_approval.fiscal_document_type or "tpv_ticket")
            root.set("date", doc_approval.created_at.isoformat() if doc_approval.created_at else "")
            
            content_elem = Element("Content")
            for key, value in document_content.items():
                item = Element(key)
                if isinstance(value, dict):
                    item.text = json.dumps(value)
                else:
                    item.text = str(value)
                content_elem.append(item)
            root.append(content_elem)
            
            export_data = tostring(root, encoding='unicode')
            content_type = "application/xml"
            filename = f"fiscal_document_{document_id}.xml"
        elif format == "pdf":
            # Para PDF, retornar JSON por ahora (generación PDF requiere librería adicional)
            # En producción, usar reportlab o similar
            export_data = json.dumps(document_content, ensure_ascii=False, indent=2)
            content_type = "application/json"
            filename = f"fiscal_document_{document_id}.json"
            # TODO: Implementar generación PDF real
        
        # Actualizar estado a 'exported'
        doc_approval.status = DocumentStatus.EXPORTED.value
        doc_approval.export_format = format
        doc_approval.exported_at = datetime.utcnow()
        
        # Agregar evento al log
        audit_log = doc_approval.audit_log
        audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "document_exported",
            "format": format,
            "exported_by": current_user.email
        })
        doc_approval.audit_log = audit_log
        
        db.commit()
        db.refresh(doc_approval)
        
        logger.info(f"📤 Documento fiscal {document_id} exportado en formato {format} por usuario {current_user.id}")
        
        return {
            "success": True,
            "document_id": document_id,
            "format": format,
            "filename": filename,
            "content_type": content_type,
            "export_data": export_data,
            "exported_at": doc_approval.exported_at.isoformat() if doc_approval.exported_at else None,
            "message": f"Documento exportado correctamente en formato {format}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if db:
            db.rollback()
        logger.error(f"Error exportando documento fiscal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error exportando documento: {str(e)}"
        )


@router.get("/{document_id}/trace")
async def get_fiscal_document_trace(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtener trazabilidad completa de un documento fiscal.
    Retorna quién, cuándo, qué acción en cada paso del flujo.
    """
    try:
        from app.models.document_approval import DocumentApproval
        
        # Buscar documento del usuario
        doc_approval = db.query(DocumentApproval).filter(
            DocumentApproval.id == document_id,
            DocumentApproval.user_id == current_user.id
        ).first()
        
        if not doc_approval:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado o no tienes permisos para acceder"
            )
        
        # Construir trazabilidad desde audit_log
        trace = {
            "document_id": document_id,
            "ticket_id": doc_approval.ticket_id,
            "fiscal_document_type": doc_approval.fiscal_document_type,
            "status": doc_approval.status,
            "agent_name": doc_approval.agent_name,
            "timeline": doc_approval.audit_log or [],
            "created_at": doc_approval.created_at.isoformat() if doc_approval.created_at else None,
            "approved_at": doc_approval.approved_at.isoformat() if doc_approval.approved_at else None,
            "sent_at": doc_approval.sent_at.isoformat() if doc_approval.sent_at else None,
            "exported_at": doc_approval.exported_at.isoformat() if doc_approval.exported_at else None,
            "filed_external_at": doc_approval.filed_external_at.isoformat() if doc_approval.filed_external_at else None
        }
        
        return {
            "success": True,
            "trace": trace,
            "message": "Trazabilidad completa del documento fiscal"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo trazabilidad: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo trazabilidad: {str(e)}"
        )

