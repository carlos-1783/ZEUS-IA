"""
🛡️ Legal-Fiscal Firewall
Protección para RAFAEL y JUSTICIA: generación en modo borrador + aprobación explícita del cliente + envío seguro al asesor indicado.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from enum import Enum
import json
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DocumentStatus(str, Enum):
    """Estado de un documento en el firewall"""
    DRAFT = "draft"  # Borrador generado, esperando aprobación
    PENDING_APPROVAL = "pending_approval"  # Enviado para aprobación del cliente
    PENDING_REVIEW = "pending_review"  # Pendiente de revisión (alias de pending_approval)
    APPROVED = "approved"  # Aprobado por el cliente
    APPROVED_BY_MANAGER = "approved_by_manager"  # Aprobado por gestor/manager
    REJECTED = "rejected"  # Rechazado por el cliente
    SENT_TO_ADVISOR = "sent_to_advisor"  # Enviado al asesor
    EXPORTED = "exported"  # Documento exportado (JSON/XML/PDF) para gestor
    FILED_EXTERNAL = "filed_external"  # Gestor confirmó presentación externa (Hacienda)
    FAILED = "failed"  # Error en el proceso


class LegalFiscalFirewall:
    """
    Firewall que garantiza que RAFAEL y JUSTICIA:
    1. Generan documentos solo en modo borrador
    2. Requieren aprobación explícita del cliente
    3. Envían documentos solo después de aprobación al asesor indicado
    4. Registran todo en logs de auditoría
    """
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _heal_document_approvals_schema_if_needed(self) -> bool:
        """
        Autorreparación mínima para entornos desalineados (sin columnas de fiscal en document_approvals).
        Devuelve True si ejecutó intento de reparación.
        """
        if not self.db:
            return False
        try:
            bind = self.db.get_bind()
            dialect = bind.dialect.name.lower()
            if "postgres" in dialect:
                statements = [
                    'ALTER TABLE document_approvals ADD COLUMN IF NOT EXISTS ticket_id VARCHAR(100)',
                    'ALTER TABLE document_approvals ADD COLUMN IF NOT EXISTS fiscal_document_type VARCHAR(50)',
                    'ALTER TABLE document_approvals ADD COLUMN IF NOT EXISTS export_format VARCHAR(20)',
                    'ALTER TABLE document_approvals ADD COLUMN IF NOT EXISTS exported_at TIMESTAMPTZ',
                    'ALTER TABLE document_approvals ADD COLUMN IF NOT EXISTS filed_external_at TIMESTAMPTZ',
                    'CREATE INDEX IF NOT EXISTS ix_document_approvals_ticket_id ON document_approvals(ticket_id)',
                ]
            else:
                # SQLite no siempre soporta IF NOT EXISTS en ADD COLUMN; usar estrategia tolerante.
                statements = [
                    'ALTER TABLE document_approvals ADD COLUMN ticket_id TEXT',
                    'ALTER TABLE document_approvals ADD COLUMN fiscal_document_type TEXT',
                    'ALTER TABLE document_approvals ADD COLUMN export_format TEXT',
                    'ALTER TABLE document_approvals ADD COLUMN exported_at TIMESTAMP',
                    'ALTER TABLE document_approvals ADD COLUMN filed_external_at TIMESTAMP',
                    'CREATE INDEX IF NOT EXISTS ix_document_approvals_ticket_id ON document_approvals(ticket_id)',
                ]

            for sql in statements:
                try:
                    self.db.execute(text(sql))
                except Exception as inner:
                    msg = str(inner).lower()
                    if "already exists" in msg or "duplicate column" in msg or "duplicate" in msg:
                        continue
                    # Seguimos para intentar el resto; puede faltar solo una parte
                    logger.warning("[FIREWALL] schema-heal warning: %s :: %s", sql, inner)
            self.db.commit()
            logger.warning("[FIREWALL] document_approvals schema-heal aplicado")
            return True
        except Exception as e:
            logger.error("[FIREWALL] schema-heal falló: %s", e)
            try:
                self.db.rollback()
            except Exception:
                pass
            return False
    
    def generate_draft_document(
        self,
        agent_name: str,  # "RAFAEL" o "JUSTICIA"
        user_id: int,
        document_type: str,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generar documento en modo borrador y persistirlo en BD.
        NO ejecuta envíos ni firmas automáticas.
        
        Returns:
            Dict con el documento en borrador y metadata de aprobación
        """
        logger.info(f"[FIREWALL] {agent_name} generando borrador: {document_type} para usuario {user_id}")
        
        # Obtener email del asesor según el agente
        advisor_email = self._get_advisor_email(user_id, agent_name)
        
        # Crear documento en borrador
        draft_document = {
            "agent": agent_name,
            "document_type": document_type,
            "status": DocumentStatus.DRAFT.value,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "requires_approval": True,
            "draft_only": True,
            "note": "Este documento es un borrador. Requiere aprobación explícita del cliente antes de enviarse al asesor."
        }
        
        # Persistir en base de datos
        document_id = None
        if self.db:
            try:
                from app.models.document_approval import DocumentApproval
                import uuid
                
                doc_approval = DocumentApproval(
                    user_id=user_id,
                    agent_name=agent_name,
                    document_type=document_type,
                    document_payload=draft_document,
                    status=DocumentStatus.DRAFT.value,
                    advisor_email=advisor_email
                )
                
                # Inicializar log de auditoría
                doc_approval.audit_log = [{
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "document_generated",
                    "agent": agent_name,
                    "status": DocumentStatus.DRAFT.value
                }]
                
                self.db.add(doc_approval)
                self.db.commit()
                self.db.refresh(doc_approval)
                
                document_id = doc_approval.id
                logger.info(f"[FIREWALL] ✅ Documento persistido con ID: {document_id}")
                
            except Exception as e:
                logger.error(f"[FIREWALL] ⚠️ Error persistiendo documento: {e}")
                if self.db:
                    self.db.rollback()
                try:
                    from services.activity_logger import ActivityLogger
                    ActivityLogger.log_activity(
                        agent_name=agent_name,
                        action_type="document_draft_persist_failed",
                        action_description=f"Fallo persistiendo borrador {document_type}",
                        details={"error": str(e), "document_type": document_type},
                        metrics={"persist_errors": 1},
                        user_email=self._get_user_email(user_id),
                        status="failed",
                        priority="high",
                        visible_to_client=True,
                    )
                except Exception:
                    pass
                # Autorreparar schema y reintentar una sola vez si es fallo por columna ausente.
                em = str(e).lower()
                if "undefinedcolumn" in em or "column" in em and "does not exist" in em:
                    healed = self._heal_document_approvals_schema_if_needed()
                    if healed and self.db:
                        try:
                            from app.models.document_approval import DocumentApproval
                            doc_approval = DocumentApproval(
                                user_id=user_id,
                                agent_name=agent_name,
                                document_type=document_type,
                                document_payload=draft_document,
                                status=DocumentStatus.DRAFT.value,
                                advisor_email=advisor_email,
                            )
                            doc_approval.audit_log = [{
                                "timestamp": datetime.utcnow().isoformat(),
                                "event": "document_generated",
                                "agent": agent_name,
                                "status": DocumentStatus.DRAFT.value
                            }]
                            self.db.add(doc_approval)
                            self.db.commit()
                            self.db.refresh(doc_approval)
                            document_id = doc_approval.id
                            logger.info(f"[FIREWALL] ✅ Documento persistido tras schema-heal, ID: {document_id}")
                        except Exception as retry_e:
                            logger.error(f"[FIREWALL] ⚠️ Reintento persistencia falló: {retry_e}")
                            self.db.rollback()
                # Continuar sin persistencia si falla (modo degradado)
        
        # Guardar en logs de auditoría
        self._log_document_generation(user_id, agent_name, document_type, draft_document)
        
        return {
            "success": True,
            "document": draft_document,
            "document_id": document_id,
            "requires_client_approval": True,
            "message": f"Documento generado en modo borrador. Requiere aprobación del cliente antes de enviarse al asesor."
        }
    
    def request_client_approval(
        self,
        user_id: int,
        document_id: str,
        agent_name: str,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Solicitar aprobación del cliente para un documento.
        Actualiza el estado del documento a PENDING_APPROVAL.
        """
        logger.info(f"[FIREWALL] Solicitando aprobación cliente para documento {document_id}")
        
        # Actualizar estado en BD si existe
        if self.db and document_id:
            try:
                from app.models.document_approval import DocumentApproval
                
                # Si document_id es string UUID, buscar por otros campos
                if isinstance(document_id, str) and not document_id.isdigit():
                    # Buscar por user_id, agent_name y status draft más reciente
                    doc = self.db.query(DocumentApproval).filter(
                        DocumentApproval.user_id == user_id,
                        DocumentApproval.agent_name == agent_name,
                        DocumentApproval.document_type == document_type,
                        DocumentApproval.status == DocumentStatus.DRAFT.value
                    ).order_by(DocumentApproval.created_at.desc()).first()
                else:
                    # Buscar por ID numérico
                    doc = self.db.query(DocumentApproval).filter(
                        DocumentApproval.id == int(document_id),
                        DocumentApproval.user_id == user_id
                    ).first()
                
                if doc:
                    doc.status = DocumentStatus.PENDING_APPROVAL.value
                    # Agregar evento al log
                    audit_log = doc.audit_log
                    audit_log.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "event": "approval_requested",
                        "status": DocumentStatus.PENDING_APPROVAL.value
                    })
                    doc.audit_log = audit_log
                    self.db.commit()
                    self.db.refresh(doc)
                    document_id = doc.id
                    logger.info(f"[FIREWALL] ✅ Estado actualizado a PENDING_APPROVAL para documento {document_id}")
            except Exception as e:
                logger.error(f"[FIREWALL] ⚠️ Error actualizando estado: {e}")
                if self.db:
                    self.db.rollback()
        
        approval_request = {
            "document_id": document_id,
            "user_id": user_id,
            "agent": agent_name,
            "document_type": document_type,
            "status": DocumentStatus.PENDING_APPROVAL.value,
            "created_at": datetime.utcnow().isoformat(),
            "approval_button_label": self._get_approval_button_label(agent_name)
        }
        
        self._log_approval_request(user_id, str(document_id), approval_request)
        
        return {
            "success": True,
            "approval_request": approval_request,
            "message": "Documento pendiente de aprobación del cliente"
        }
    
    async def approve_and_send_to_advisor(
        self,
        user_id: int,
        document_id: str,
        user_email: str,
        agent_name: str,
        document_content: Dict[str, Any],
        advisor_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aprobar documento y enviarlo al asesor indicado.
        Solo se ejecuta después de aprobación explícita del cliente.
        """
        logger.info(f"[FIREWALL] Aprobación recibida para documento {document_id}")
        
        # Obtener documento de BD
        doc_approval = None
        if self.db and document_id:
            try:
                from app.models.document_approval import DocumentApproval
                
                # Buscar documento
                if isinstance(document_id, str) and document_id.isdigit():
                    doc_approval = self.db.query(DocumentApproval).filter(
                        DocumentApproval.id == int(document_id),
                        DocumentApproval.user_id == user_id
                    ).first()
                else:
                    # Buscar por user_id y agent_name más reciente pendiente
                    doc_approval = self.db.query(DocumentApproval).filter(
                        DocumentApproval.user_id == user_id,
                        DocumentApproval.agent_name == agent_name,
                        DocumentApproval.status.in_([DocumentStatus.DRAFT.value, DocumentStatus.PENDING_APPROVAL.value])
                    ).order_by(DocumentApproval.created_at.desc()).first()
                
                if doc_approval:
                    # Usar contenido del documento persistido si no se proporciona
                    if not document_content:
                        document_content = doc_approval.document_payload.get("content", {})
            except Exception as e:
                logger.error(f"[FIREWALL] ⚠️ Error obteniendo documento: {e}")
        
        # Obtener email del asesor según el agente
        if not advisor_email:
            advisor_email = self._get_advisor_email(user_id, agent_name)
            # Si tenemos doc_approval, usar su advisor_email si existe
            if doc_approval and doc_approval.advisor_email:
                advisor_email = doc_approval.advisor_email
        
        if not advisor_email:
            return {
                "success": False,
                "error": "Falta email de asesor. Proporcione un contacto para enviar.",
                "status": "pending_advisor_email"
            }
        
        # Marcar como aprobado en BD
        approval_record = {
            "document_id": document_id,
            "user_id": user_id,
            "user_email": user_email,
            "agent": agent_name,
            "status": DocumentStatus.APPROVED.value,
            "approved_at": datetime.utcnow().isoformat(),
            "advisor_email": advisor_email,
            "approval_effect": "Otorga permiso expreso para enviar el documento al asesor indicado. No equivale a firma legal."
        }
        
        # Actualizar estado en BD
        if doc_approval:
            try:
                doc_approval.status = DocumentStatus.APPROVED.value
                doc_approval.approved_at = datetime.utcnow()
                doc_approval.advisor_email = advisor_email
                
                # Agregar evento al log
                audit_log = doc_approval.audit_log
                audit_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "document_approved",
                    "user_email": user_email,
                    "advisor_email": advisor_email
                })
                doc_approval.audit_log = audit_log
                
                self.db.commit()
                self.db.refresh(doc_approval)
                document_id = doc_approval.id
            except Exception as e:
                logger.error(f"[FIREWALL] ⚠️ Error actualizando aprobación: {e}")
                if self.db:
                    self.db.rollback()
        
        # Enviar al asesor
        send_result = await self._send_to_advisor(
            advisor_email=advisor_email,
            agent_name=agent_name,
            document_content=document_content,
            user_email=user_email,
            metadata=approval_record
        )
        
        # Actualizar estado final en BD
        if doc_approval:
            try:
                if send_result.get("success"):
                    # Si el documento fue exportado, mantener estado exported, sino sent_to_advisor
                    if doc_approval.status == DocumentStatus.EXPORTED.value:
                        # Ya está exportado, solo marcar como enviado
                        doc_approval.sent_at = datetime.utcnow()
                        approval_record["status"] = DocumentStatus.EXPORTED.value
                        approval_record["sent_at"] = datetime.utcnow().isoformat()
                    else:
                        doc_approval.status = DocumentStatus.SENT_TO_ADVISOR.value
                        doc_approval.sent_at = datetime.utcnow()
                        approval_record["status"] = DocumentStatus.SENT_TO_ADVISOR.value
                        approval_record["sent_at"] = datetime.utcnow().isoformat()
                else:
                    doc_approval.status = DocumentStatus.FAILED.value
                    approval_record["status"] = DocumentStatus.FAILED.value
                    approval_record["error"] = send_result.get("error")
                
                # Agregar evento al log
                audit_log = doc_approval.audit_log
                audit_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "sent_to_advisor" if send_result.get("success") else "send_failed",
                    "advisor_email": advisor_email,
                    "success": send_result.get("success", False),
                    "error": send_result.get("error") if not send_result.get("success") else None
                })
                doc_approval.audit_log = audit_log
                
                self.db.commit()
                self.db.refresh(doc_approval)
            except Exception as e:
                logger.error(f"[FIREWALL] ⚠️ Error actualizando estado final: {e}")
                if self.db:
                    self.db.rollback()
        else:
            # Fallback si no hay doc_approval
            if send_result.get("success"):
                approval_record["status"] = DocumentStatus.SENT_TO_ADVISOR.value
                approval_record["sent_at"] = datetime.utcnow().isoformat()
            else:
                approval_record["status"] = DocumentStatus.FAILED.value
                approval_record["error"] = send_result.get("error")
        
        # Log de auditoría
        self._log_approval_action(user_id, str(document_id), approval_record)
        
        return {
            "success": send_result.get("success", False),
            "approval_record": approval_record,
            "send_result": send_result,
            "message": "Documento aprobado y enviado al asesor" if send_result.get("success") else "Error al enviar al asesor"
        }
    
    def _get_approval_button_label(self, agent_name: str) -> str:
        """Obtener etiqueta del botón de aprobación según el agente"""
        labels = {
            "RAFAEL": "Aprobar y Enviar al Asesor Fiscal",
            "JUSTICIA": "Aprobar y Enviar al Abogado"
        }
        return labels.get(agent_name, "Aprobar y Enviar al Asesor")
    
    def _get_advisor_email(self, user_id: int, agent_name: str) -> Optional[str]:
        """Obtener email del asesor desde la BD del usuario"""
        if not self.db:
            return None
        
        try:
            from app.models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return None
            
            if agent_name == "RAFAEL":
                return user.email_gestor_fiscal
            elif agent_name == "JUSTICIA":
                return user.email_asesor_legal
            
            return None
        except Exception as e:
            logger.error(f"[FIREWALL] Error obteniendo email asesor: {e}")
            return None

    def _get_user_email(self, user_id: int) -> Optional[str]:
        """Obtener email del cliente para enlazar actividad visible en panel."""
        if not self.db:
            return None
        try:
            from app.models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            return user.email if user else None
        except Exception as e:
            logger.error(f"[FIREWALL] Error obteniendo email usuario: {e}")
            return None
    
    async def _send_to_advisor(
        self,
        advisor_email: str,
        agent_name: str,
        document_content: Dict[str, Any],
        user_email: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enviar documento al asesor por email.
        Incluye PDF/JSON como attachments y metadata.
        """
        try:
            from services.email_service import email_service
            
            if not email_service.is_configured():
                logger.warning("[FIREWALL] Email service no configurado, simulando envío")
                return {
                    "success": True,
                    "simulated": True,
                    "message": "Envío simulado (email service no configurado)"
                }
            
            # Preparar email
            subject = f"[ZEUS-IA] Documento {agent_name} - Requiere revisión"
            
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }}
                    .header {{ background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 20px; color: white; }}
                    .content {{ padding: 30px; background: #f9fafb; }}
                    .document-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    .footer {{ padding: 20px; text-align: center; background: #e5e7eb; font-size: 12px; color: #6b7280; }}
                    .warning {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>⚡ ZEUS-IA</h1>
                    <p>Documento {agent_name} - Requiere revisión</p>
                </div>
                
                <div class="content">
                    <p>Estimado/a asesor,</p>
                    
                    <p>El cliente <strong>{user_email}</strong> ha aprobado el siguiente documento generado por {agent_name} y solicita su revisión:</p>
                    
                    <div class="document-box">
                        <h3>Tipo de documento:</h3>
                        <p>{metadata.get('document_type', 'N/A')}</p>
                        
                        <h3>Contenido:</h3>
                        <pre>{json.dumps(document_content, indent=2, ensure_ascii=False)}</pre>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ IMPORTANTE:</strong><br>
                        Este documento fue generado por IA en modo borrador y aprobado por el cliente para su revisión.
                        La responsabilidad final sobre presentación y firma recae en el asesor humano.
                        ZEUS-IA no actúa como representante legal.
                    </div>
                    
                    <p>Por favor, revise el documento y proceda según corresponda.</p>
                    
                    <p>Saludos,<br>El equipo de ZEUS-IA</p>
                </div>
                
                <div class="footer">
                    <p>Este email fue enviado automáticamente por ZEUS-IA tras aprobación explícita del cliente.</p>
                    <p>© 2025 ZEUS-IA. Todos los derechos reservados.</p>
                </div>
            </body>
            </html>
            """
            
            # Enviar email (async)
            result = await email_service.send_email(
                to_email=advisor_email,
                subject=subject,
                content=html_content,
                content_type="text/html"
            )
            
            return {
                "success": result.get("success", False),
                "advisor_email": advisor_email,
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[FIREWALL] Error enviando a asesor: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _log_document_generation(
        self,
        user_id: int,
        agent_name: str,
        document_type: str,
        document: Dict[str, Any]
    ):
        """Registrar generación de documento en logs y en actividad visible al cliente."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "document_generated",
            "user_id": user_id,
            "agent": agent_name,
            "document_type": document_type,
            "status": DocumentStatus.DRAFT.value,
            "metadata": document
        }
        logger.info(f"[AUDIT] {json.dumps(log_entry)}")
        # También registrar en AgentActivity para pestaña "Actividad" del workspace.
        try:
            from services.activity_logger import ActivityLogger
            user_email = self._get_user_email(user_id)
            status = "completed" if document.get("status") == DocumentStatus.DRAFT.value else "pending"
            ticket_id = (
                (document.get("metadata") or {}).get("ticket_id")
                or (document.get("content") or {}).get("ticket_id")
            )
            ActivityLogger.log_activity(
                agent_name=agent_name,
                action_type="document_draft_generated",
                action_description=f"Borrador {document_type} generado para aprobación del cliente",
                details={
                    "document_type": document_type,
                    "ticket_id": ticket_id,
                    "requires_approval": document.get("requires_approval", True),
                    "draft_only": document.get("draft_only", True),
                },
                metrics={"draft_generated": 1},
                user_email=user_email,
                status=status,
                priority="normal",
                visible_to_client=True,
            )
        except Exception as e:
            logger.warning(f"[FIREWALL] No se pudo registrar AgentActivity de borrador: {e}")
    
    def _log_approval_request(
        self,
        user_id: int,
        document_id: str,
        approval_request: Dict[str, Any]
    ):
        """Registrar solicitud de aprobación"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "approval_requested",
            "user_id": user_id,
            "document_id": document_id,
            "metadata": approval_request
        }
        logger.info(f"[AUDIT] {json.dumps(log_entry)}")
    
    def _log_approval_action(
        self,
        user_id: int,
        document_id: str,
        approval_record: Dict[str, Any]
    ):
        """Registrar acción de aprobación en auditoría y actividad."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "approval_action",
            "user_id": user_id,
            "document_id": document_id,
            "metadata": approval_record
        }
        logger.info(f"[AUDIT] {json.dumps(log_entry)}")
        try:
            from services.activity_logger import ActivityLogger
            user_email = self._get_user_email(user_id)
            status = approval_record.get("status", "completed")
            ActivityLogger.log_activity(
                agent_name=approval_record.get("agent", "ZEUS"),
                action_type="document_approval_action",
                action_description=f"Documento {document_id} -> {status}",
                details={"document_id": document_id, **approval_record},
                metrics={"approval_actions": 1},
                user_email=user_email,
                status="completed" if status in ("approved", "sent_to_advisor", "exported") else "pending",
                priority="normal",
                visible_to_client=True,
            )
        except Exception as e:
            logger.warning(f"[FIREWALL] No se pudo registrar AgentActivity de aprobación: {e}")


# Instancia global del firewall
firewall = LegalFiscalFirewall()

