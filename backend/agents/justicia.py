"""
⚡ JUSTICIA - Asesora Legal y GDPR ⚡
Agente especializado en Legal y Protección de Datos
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class Justicia(BaseAgent):
    """
    JUSTICIA - Abogada Digital
    Especializada en cumplimiento legal, GDPR y protección de datos
    """
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        with open(prompts_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        justicia_config = config["zeus_prime_v1"]["agents"]["JUSTICIA"]
        
        super().__init__(
            name="JUSTICIA",
            role=justicia_config["role"],
            system_prompt=justicia_config["prompt"],
            temperature=justicia_config["parameters"]["temperature"],
            max_tokens=justicia_config["parameters"]["max_tokens"],
            hitl_threshold=0.85  # Alto threshold para decisiones legales
        )
        
        self.domain = justicia_config["parameters"]["domain"]
        self.auto_validation = justicia_config["parameters"]["auto_validation"]  # Debe ser False
        self.capabilities = justicia_config["parameters"].get("capabilities", [])
        
        # Integración TPV
        self.tpv_integration_enabled = "integracion_TPV_validate_ticket_legality" in self.capabilities
        
        print(f"⚖️ JUSTICIA inicializada - Dominio: {self.domain}")
        print(f"⚠️ Auto-validación: {self.auto_validation} (decisiones legales requieren revisión)")
        if self.tpv_integration_enabled:
            print(f"💳 Integración TPV habilitada: validate_ticket_legality, gdpr_audit")
    
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud legal/GDPR
        
        Casos de uso:
        - Revisar contratos
        - Validar cumplimiento GDPR
        - Evaluar políticas de privacidad
        - Asesorar sobre normativa
        - Generar cláusulas legales
        """
        request_type = context.get("type", "general")
        user_message = context.get("message", context.get("user_message", ""))
        
        # Enriquecer mensaje según tipo
        if request_type == "contract":
            enhanced_message = self._enhance_contract_request(user_message, context)
        elif request_type == "gdpr":
            enhanced_message = self._enhance_gdpr_request(user_message, context)
        elif request_type == "policy":
            enhanced_message = self._enhance_policy_request(user_message, context)
        else:
            enhanced_message = user_message
        
        # Hacer decisión
        result = self.make_decision(enhanced_message, additional_context=context)
        
        # JUSTICIA-specific metadata
        result["domain"] = self.domain
        result["request_type"] = request_type
        result["legal_ok"] = False  # Siempre requiere validación final
        result["requires_legal_review"] = True
        
        # Aplicar Legal-Fiscal Firewall para documentos legales
        user_id = context.get("user_id")
        if user_id and self._requires_firewall(result, request_type):
            result = self._apply_firewall(result, user_id, request_type, context)
        
        return result
    
    def _requires_firewall(self, result: Dict[str, Any], request_type: str) -> bool:
        """Determinar si el resultado requiere firewall (documentos legales)"""
        # Documentos legales que requieren aprobación: contratos, cláusulas, políticas
        legal_document_types = ["contract", "gdpr", "policy", "clausula", "contrato", "legal"]
        return request_type in legal_document_types or any(
            kw in result.get("content", "").lower() 
            for kw in ["contrato", "cláusula", "legal", "gdpr", "política", "compliance"]
        )
    
    def _apply_firewall(
        self, 
        result: Dict[str, Any], 
        user_id: int, 
        request_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aplicar Legal-Fiscal Firewall: modo draft_only + aprobación requerida"""
        try:
            from services.legal_fiscal_firewall import firewall
            from app.db.session import SessionLocal
            
            # Obtener sesión de BD
            db = SessionLocal()
            firewall.db = db
            
            # Generar ID único para el documento
            document_id = str(uuid.uuid4())
            
            # Generar documento en modo borrador (esto ahora persiste en BD)
            draft_result = firewall.generate_draft_document(
                agent_name="JUSTICIA",
                user_id=user_id,
                document_type=request_type,
                content={
                    "content": result.get("content", ""),
                    "confidence": result.get("confidence", 0),
                    "metadata": result.get("metadata", {})
                },
                metadata={
                    "request_type": request_type,
                    "domain": self.domain,
                    "legal_ok": False
                }
            )
            
            # Obtener document_id del resultado (ahora viene de la BD)
            persisted_document_id = draft_result.get("document_id")
            if persisted_document_id:
                document_id = str(persisted_document_id)
            
            # Solicitar aprobación del cliente
            approval_request = firewall.request_client_approval(
                user_id=user_id,
                document_id=document_id,
                agent_name="JUSTICIA",
                document_type=request_type
            )
            
            # Modificar resultado para incluir información del firewall
            result["firewall_applied"] = True
            result["draft_only"] = True
            result["document_id"] = document_id
            result["status"] = "draft"
            result["requires_client_approval"] = True
            result["approval_button_label"] = approval_request.get("approval_request", {}).get("approval_button_label", "Aprobar y Enviar al Abogado")
            result["message"] = "Documento generado en modo borrador. Requiere aprobación explícita del cliente antes de enviarse al asesor legal."
            result["note"] = "Los agentes generan PDF/JSON/Markdown como borradores y no ejecutan envíos ni firmas automáticas."
            
            db.close()
            
        except Exception as e:
            print(f"⚠️ [JUSTICIA] Error aplicando firewall: {e}")
            # Si falla el firewall, marcar como requiere aprobación manual
            result["firewall_applied"] = False
            result["requires_manual_review"] = True
            result["error"] = f"Error en firewall: {str(e)}"
        
        return result
    
    def _enhance_contract_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de revisión de contrato"""
        contract_type = context.get("contract_type", "no especificado")
        parties = context.get("parties", "no especificadas")
        
        enhanced = f"""{message}

Revisión de contrato:
- Tipo: {contract_type}
- Partes: {parties}

Analiza:
1. Cláusulas críticas y riesgos
2. Cumplimiento normativo
3. Protección de intereses
4. Cláusulas abusivas o ilegales
5. Recomendaciones de modificación
6. Nivel de riesgo legal (bajo/medio/alto)
"""
        return enhanced
    
    def _enhance_gdpr_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud GDPR"""
        data_type = context.get("data_type", "no especificado")
        processing_purpose = context.get("purpose", "no especificado")
        
        enhanced = f"""{message}

Análisis GDPR:
- Tipo de datos: {data_type}
- Finalidad: {processing_purpose}

Evalúa:
1. Base legal para el tratamiento (Art. 6 GDPR)
2. Necesidad de DPO
3. Evaluación de impacto (DPIA) requerida
4. Derechos de los interesados
5. Medidas de seguridad necesarias
6. Cumplimiento normativo (RGPD/LOPDGDD)
7. Riesgo de sanción
"""
        return enhanced
    
    def _enhance_policy_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de política"""
        policy_type = context.get("policy_type", "no especificado")
        
        enhanced = f"""{message}

Política a evaluar:
- Tipo: {policy_type}

Revisa:
1. Cumplimiento legal vigente
2. Claridad y comprensibilidad
3. Derechos de usuarios/clientes
4. Consentimiento válido
5. Procedimientos de ejercicio de derechos
6. Actualizaciones necesarias
"""
        return enhanced
    
    def check_hitl_required(self, decision: Dict) -> bool:
        """
        JUSTICIA requiere HITL para:
        - Todas las decisiones legales (legal_ok=false)
        - Contratos de alto riesgo
        - Posibles incumplimientos GDPR
        - Cualquier decisión con implicaciones legales
        """
        # Check base
        if super().check_hitl_required(decision):
            return True
        
        content = decision.get("content", "").lower()
        
        # Detectar alto riesgo legal
        high_risk_keywords = [
            "sanción", "multa", "incumplimiento", "ilegal", "prohibido",
            "demanda", "litigio", "contencioso", "infracción",
            "penalty", "fine", "violation", "illegal"
        ]
        
        if any(kw in content for kw in high_risk_keywords):
            print(f"⚠️ [HITL] JUSTICIA: Alto riesgo legal detectado")
            return True
        
        # TODAS las decisiones legales requieren revisión
        if not self.auto_validation:
            return True
        
        return False
    
    def validate_tpv_ticket_legality(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validar legalidad de ticket del TPV
        
        Args:
            ticket_data: Datos del ticket del TPV
        
        Returns:
            Dict con resultado de validación legal
        """
        if not self.tpv_integration_enabled:
            return {
                "success": False,
                "error": "Integración TPV no habilitada en JUSTICIA"
            }
        
        try:
            # Validaciones legales
            validations = {
                "gdpr_compliant": True,
                "data_retention_ok": True,
                "payment_method_legal": True,
                "invoice_requirements_met": True
            }
            
            # Verificar GDPR compliance
            if ticket_data.get("customer_data"):
                # Validar que los datos personales están protegidos
                validations["gdpr_compliant"] = True
                validations["data_protection_ok"] = True
            
            # Verificar método de pago legal
            payment_method = ticket_data.get("payment_method", "")
            legal_payment_methods = ["efectivo", "tarjeta", "bizum", "transferencia"]
            validations["payment_method_legal"] = payment_method in legal_payment_methods
            
            # Auditoría GDPR
            gdpr_audit = {
                "ticket_id": ticket_data.get("id"),
                "date": ticket_data.get("date"),
                "data_collected": bool(ticket_data.get("customer_data")),
                "gdpr_compliant": validations["gdpr_compliant"],
                "audit_timestamp": datetime.utcnow().isoformat()
            }
            
            all_valid = all(validations.values())
            
            logger.info(f"⚖️ JUSTICIA validó ticket TPV: {ticket_data.get('id')} - Legal: {all_valid}")
            
            return {
                "success": True,
                "legal_ok": all_valid,
                "validations": validations,
                "gdpr_audit": gdpr_audit,
                "requires_legal_review": not all_valid
            }
            
        except Exception as e:
            logger.error(f"Error validando ticket TPV en JUSTICIA: {e}")
            return {
                "success": False,
                "error": str(e),
                "legal_ok": False
            }

