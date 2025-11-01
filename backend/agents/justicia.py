"""
⚡ JUSTICIA - Asesora Legal y GDPR ⚡
Agente especializado en Legal y Protección de Datos
"""

import json
from typing import Dict, Any
from backend.agents.base_agent import BaseAgent


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
        
        print(f"⚖️ JUSTICIA inicializada - Dominio: {self.domain}")
        print(f"⚠️ Auto-validación: {self.auto_validation} (decisiones legales requieren revisión)")
    
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

