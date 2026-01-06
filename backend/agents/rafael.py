"""
⚡ RAFAEL - Guardián Fiscal ⚡
Agente especializado en Fiscalidad y Contabilidad
"""

import json
import uuid
import logging
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class Rafael(BaseAgent):
    """
    RAFAEL - Guardián fiscal
    Especializado en fiscalidad española, contabilidad y cumplimiento
    """
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        with open(prompts_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        rafael_config = config["zeus_prime_v1"]["agents"]["RAFAEL"]
        
        super().__init__(
            name="RAFAEL",
            role=rafael_config["role"],
            system_prompt=rafael_config["prompt"],
            temperature=rafael_config["parameters"]["temperature"],
            max_tokens=rafael_config["parameters"]["max_tokens"],
            hitl_threshold=rafael_config["parameters"]["hitl_threshold"]
        )
        
        self.domain = rafael_config["parameters"]["domain"]
        self.country = rafael_config["parameters"]["country"]
        self.capabilities = rafael_config["parameters"].get("capabilities", [])
        
        # Integración TPV
        self.tpv_integration_enabled = "integracion_TPV_auto_accounting" in self.capabilities
        
        print(f"📊 RAFAEL inicializado - Dominio: {self.domain} ({self.country})")
        if self.tpv_integration_enabled:
            print(f"💳 Integración TPV habilitada: auto_accounting, modelo_303_support")
    
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud fiscal/contable
        
        Casos de uso:
        - Generar facturas
        - Analizar gastos deducibles
        - Calcular IVA/IRPF
        - Asesorar sobre modelos (303, 390, etc.)
        - Optimización fiscal
        """
        request_type = context.get("type", "general")
        user_message = context.get("message", context.get("user_message", ""))
        
        # Si es comunicación entre agentes, procesar directamente
        if context.get("inter_agent_communication"):
            enhanced_message = user_message
        else:
            # Agregar contexto específico fiscal si es necesario
            if request_type == "invoice":
                enhanced_message = self._enhance_invoice_request(user_message, context)
            elif request_type == "tax":
                enhanced_message = self._enhance_tax_request(user_message, context)
            elif request_type == "deduction":
                enhanced_message = self._enhance_deduction_request(user_message, context)
            else:
                enhanced_message = user_message
            
            # Detectar si necesita ayuda de otros agentes
            needs_legal_help = any(kw in user_message.lower() for kw in [
                "legal", "contrato", "gdpr", "privacidad", "términos", "compliance", "normativa"
            ])
            needs_marketing_help = any(kw in user_message.lower() for kw in [
                "marketing", "campaña", "cliente", "venta", "promoción"
            ])
            
            # Si necesita ayuda legal, solicitar a JUSTICIA
            if needs_legal_help and self.zeus_core_ref:
                print(f"📡 [RAFAEL] Detecté necesidad de ayuda legal, consultando a JUSTICIA...")
                legal_response = self.request_agent_help(
                    "JUSTICIA",
                    f"RAFAEL necesita información legal para: {user_message}",
                    context
                )
                if legal_response and legal_response.get("success"):
                    enhanced_message += f"\n\n[Información de JUSTICIA]: {legal_response.get('content', '')[:500]}"
            
            # Si necesita ayuda de marketing, solicitar a PERSEO
            if needs_marketing_help and self.zeus_core_ref:
                print(f"📡 [RAFAEL] Detecté necesidad de ayuda de marketing, consultando a PERSEO...")
                marketing_response = self.request_agent_help(
                    "PERSEO",
                    f"RAFAEL necesita información de marketing para: {user_message}",
                    context
                )
                if marketing_response and marketing_response.get("success"):
                    enhanced_message += f"\n\n[Información de PERSEO]: {marketing_response.get('content', '')[:500]}"
        
        # Hacer decisión
        result = self.make_decision(enhanced_message, additional_context=context)
        
        # RAFAEL-specific metadata
        result["domain"] = self.domain
        result["country"] = self.country
        result["request_type"] = request_type
        
        # Aplicar Legal-Fiscal Firewall para documentos que requieren aprobación
        user_id = context.get("user_id")
        if user_id and self._requires_firewall(result, request_type):
            result = self._apply_firewall(result, user_id, request_type, context)
        
        return result
    
    def _requires_firewall(self, result: Dict[str, Any], request_type: str) -> bool:
        """Determinar si el resultado requiere firewall (documentos fiscales)"""
        # Documentos fiscales que requieren aprobación: modelos, facturas, declaraciones
        fiscal_document_types = ["invoice", "tax", "modelo", "declaracion", "factura", "303", "390"]
        return request_type in fiscal_document_types or any(
            kw in result.get("content", "").lower() 
            for kw in ["modelo", "factura", "declaración", "aeat", "hacienda"]
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
                agent_name="RAFAEL",
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
                    "country": self.country
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
                agent_name="RAFAEL",
                document_type=request_type
            )
            
            # Modificar resultado para incluir información del firewall
            result["firewall_applied"] = True
            result["draft_only"] = True
            result["document_id"] = document_id
            result["status"] = "draft"
            result["requires_client_approval"] = True
            result["approval_button_label"] = approval_request.get("approval_request", {}).get("approval_button_label", "Aprobar y Enviar al Asesor Fiscal")
            result["message"] = "Documento generado en modo borrador. Requiere aprobación explícita del cliente antes de enviarse al gestor fiscal."
            result["note"] = "Los agentes generan PDF/JSON/Markdown como borradores y no ejecutan envíos ni firmas automáticas."
            
            db.close()
            
        except Exception as e:
            print(f"⚠️ [RAFAEL] Error aplicando firewall: {e}")
            # Si falla el firewall, marcar como requiere aprobación manual
            result["firewall_applied"] = False
            result["requires_manual_review"] = True
            result["error"] = f"Error en firewall: {str(e)}"
        
        return result
    
    def _enhance_invoice_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de factura"""
        client_name = context.get("client_name", "no especificado")
        amount = context.get("amount", "no especificado")
        concept = context.get("concept", "no especificado")
        
        enhanced = f"""{message}

Datos de la factura:
- Cliente: {client_name}
- Importe: {amount}€
- Concepto: {concept}

Por favor, proporciona:
1. IVA aplicable (21%, 10%, 4% o exento)
2. Retención IRPF si aplica
3. Total a facturar
4. Formato recomendado
5. Información adicional requerida según normativa
"""
        return enhanced
    
    def _enhance_tax_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud fiscal"""
        period = context.get("period", "no especificado")
        tax_type = context.get("tax_type", "no especificado")
        
        enhanced = f"""{message}

Contexto fiscal:
- Período: {period}
- Tipo de impuesto: {tax_type}

Por favor, proporciona:
1. Normativa aplicable
2. Cálculo detallado
3. Fecha límite de presentación
4. Documentación necesaria
5. Posibles deducciones u optimizaciones
"""
        return enhanced
    
    def _enhance_deduction_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de deducción"""
        expense_type = context.get("expense_type", "no especificado")
        amount = context.get("amount", "no especificado")
        
        enhanced = f"""{message}

Gasto a analizar:
- Tipo: {expense_type}
- Importe: {amount}€

Por favor, determina:
1. ¿Es deducible? (sí/no/parcial)
2. Porcentaje de deducción aplicable
3. Requisitos para la deducción (factura, justificación, etc.)
4. IVA deducible
5. Documentación necesaria
"""
        return enhanced
    
    def check_hitl_required(self, decision: Dict) -> bool:
        """
        RAFAEL requiere HITL para:
        - Importes >5000€
        - Incertidumbre >10% en cálculos
        - Normativa ambigua
        - Decisiones que afecten declaraciones oficiales
        """
        # Check base
        if super().check_hitl_required(decision):
            return True
        
        content = decision.get("content", "").lower()
        
        # Detectar importes altos
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?', content)
        for num_str in numbers:
            try:
                amount = float(num_str.replace(',', '.'))
                if amount > 5000:
                    print(f"⚠️ [HITL] RAFAEL: Importe alto detectado (>{amount}€)")
                    return True
            except ValueError:
                pass
        
        # Detectar variaciones >10%
        if "variación" in content or "diferencia" in content:
            for num_str in numbers:
                try:
                    percentage = float(num_str.replace(',', '.'))
                    if percentage > 10:
                        print(f"⚠️ [HITL] RAFAEL: Variación >10% detectada")
                        return True
                except ValueError:
                    pass
        
        # Detectar palabras de incertidumbre fiscal
        uncertain_keywords = [
            "ambiguo", "poco claro", "interpretación", "consulta vinculante",
            "requiere asesor", "caso especial", "normativa nueva"
        ]
        if any(kw in content for kw in uncertain_keywords):
            print(f"⚠️ [HITL] RAFAEL: Incertidumbre normativa detectada")
            return True
        
        return False
    
    def process_tpv_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar datos de ticket del TPV para contabilidad automática.
        Genera libro de ingresos, resumen diario y resumen mensual en modo borrador.
        
        Args:
            ticket_data: Datos del ticket del TPV
        
        Returns:
            Dict con resultado del procesamiento fiscal (modo draft_only)
        """
        if not self.tpv_integration_enabled:
            return {
                "success": False,
                "error": "Integración TPV no habilitada en RAFAEL"
            }
        
        try:
            from datetime import datetime
            
            # Preparar datos fiscales del ticket
            ticket_date = ticket_data.get("date", datetime.utcnow().isoformat())
            if isinstance(ticket_date, str):
                try:
                    dt = datetime.fromisoformat(ticket_date.replace('Z', '+00:00'))
                except:
                    dt = datetime.utcnow()
            else:
                dt = ticket_date
            
            fiscal_data = {
                "ticket_id": ticket_data.get("id"),
                "fecha": dt.strftime("%Y-%m-%d"),
                "hora": dt.strftime("%H:%M:%S"),
                "total": ticket_data.get("totals", {}).get("total", 0),
                "subtotal": ticket_data.get("totals", {}).get("subtotal", 0),
                "iva": ticket_data.get("totals", {}).get("iva", 0),
                "método_pago": ticket_data.get("payment_method"),
                "productos": [
                    {
                        "nombre": item.get("name", ""),
                        "cantidad": item.get("quantity", 0),
                        "precio_unitario": item.get("price", 0),
                        "subtotal": item.get("subtotal", 0),
                        "iva": item.get("subtotal_with_iva", 0) - item.get("subtotal", 0),
                        "tasa_iva": item.get("iva_rate", 21),
                        "categoria": item.get("category", "")
                    }
                    for item in ticket_data.get("items", [])
                ],
                "responsable": ticket_data.get("employee_id"),
                "terminal": ticket_data.get("terminal_id"),
                "categoria": ticket_data.get("business_profile")
            }
            
            # Generar libro de ingresos (acumulado)
            libro_ingresos = {
                "fecha": fiscal_data["fecha"],
                "tickets": [fiscal_data],
                "total_dia": fiscal_data["total"],
                "iva_dia": fiscal_data["iva"],
                "metodos_pago": {
                    fiscal_data["método_pago"]: fiscal_data["total"]
                }
            }
            
            # Resumen diario
            resumen_diario = {
                "fecha": fiscal_data["fecha"],
                "total_ventas": fiscal_data["total"],
                "total_iva": fiscal_data["iva"],
                "total_sin_iva": fiscal_data["subtotal"],
                "numero_tickets": 1,
                "metodos_pago": {
                    fiscal_data["método_pago"]: fiscal_data["total"]
                },
                "categoria_negocio": fiscal_data["categoria"]
            }
            
            # Resumen mensual (estructura base, se acumulará con más tickets)
            resumen_mensual = {
                "mes": dt.strftime("%Y-%m"),
                "total_ventas": fiscal_data["total"],
                "total_iva": fiscal_data["iva"],
                "numero_tickets": 1,
                "dias_con_ventas": [fiscal_data["fecha"]]
            }
            
            # Generar entrada contable automática (modo borrador)
            accounting_entry = {
                "tipo": "venta_tpv",
                "fecha": fiscal_data["fecha"],
                "importe": fiscal_data["total"],
                "iva": fiscal_data["iva"],
                "metodo_pago": fiscal_data["método_pago"],
                "modelo_303_ready": True,
                "auto_accounting": True,
                "draft_only": True,
                "note": "Entrada generada automáticamente desde TPV. Requiere revisión del gestor fiscal antes de presentar a Hacienda."
            }
            
            logger.info(f"📊 RAFAEL procesó ticket TPV: €{fiscal_data['total']:.2f} (modo borrador)")
            
            return {
                "success": True,
                "accounting_entry": accounting_entry,
                "fiscal_data": fiscal_data,
                "libro_ingresos": libro_ingresos,
                "resumen_diario": resumen_diario,
                "resumen_mensual": resumen_mensual,
                "model_303_ready": True,
                "draft_only": True,
                "legal_disclaimer": "ZEUS no presenta impuestos ni actúa ante Hacienda. El gestor humano es responsable final de la presentación."
            }
            
        except Exception as e:
            logger.error(f"Error procesando ticket TPV en RAFAEL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            return {
                "success": False,
                "error": str(e)
            }

