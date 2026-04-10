"""
⚡ PERSEO - Estratega de Crecimiento ⚡
Agente especializado en Marketing, SEO y Growth
"""

import json
import re
from typing import Dict, Any
from agents.base_agent import BaseAgent


def _needs_fiscal_context(message: str) -> bool:
    """Evita falsos positivos (p. ej. 'modelo' en 'modelo de negocio' → no llamar a RAFAEL)."""
    low = message.lower()
    if re.search(
        r"\b(iva|irpf|factura|fiscal|hacienda|aeat|declaración|declaracion|retención|retencion)\b",
        low,
        re.I,
    ):
        return True
    if re.search(r"modelo\s*3[0-9]{2}\b", low):
        return True
    return False


def _needs_legal_context(message: str) -> bool:
    """Frases claras; \\blegal\\b no coincide dentro de 'ilegal' (sin frontera antes de 'l')."""
    low = message.lower()
    if re.search(
        r"\b(contrato|gdpr|rgpd|compliance|jurídico|juridico|litigio|demanda|abogado|notario|legal)\b",
        low,
        re.I,
    ):
        return True
    if "privacidad de datos" in low or "política de privacidad" in low or "politica de privacidad" in low:
        return True
    if "términos y condiciones" in low or "terminos y condiciones" in low:
        return True
    return False


class Perseo(BaseAgent):
    """
    PERSEO (PER-SEO) - Arquitecto del crecimiento
    Especializado en marketing digital, SEO, SEM y estrategias de crecimiento
    """
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        with open(prompts_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        perseo_config = config["zeus_prime_v1"]["agents"]["PERSEO"]
        
        super().__init__(
            name="PERSEO",
            role=perseo_config["role"],
            system_prompt=perseo_config["prompt"],
            temperature=perseo_config["parameters"]["temperature"],
            max_tokens=perseo_config["parameters"]["max_tokens"],
            hitl_threshold=0.7  # Un poco más permisivo que otros
        )
        
        self.domain = perseo_config["parameters"]["domain"]
        self.autotuning = perseo_config["parameters"].get("autotuning", True)
        
        print(f"🎯 PERSEO inicializado - Dominio: {self.domain}")
    
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud de marketing/growth
        
        Casos de uso:
        - Crear campañas de marketing
        - Optimizar SEO
        - Analizar competencia
        - Estrategias de crecimiento
        - Funnels y conversión
        """
        request_type = context.get("type", "general")
        user_message = context.get("message", context.get("user_message", ""))
        
        needs_fiscal_help = _needs_fiscal_context(user_message)
        needs_legal_help = _needs_legal_context(user_message)
        
        # Si es comunicación entre agentes, procesar directamente
        if context.get("inter_agent_communication"):
            enhanced_message = user_message
        else:
            # Agregar contexto específico de marketing si es necesario
            if request_type == "campaign":
                enhanced_message = self._enhance_campaign_request(user_message, context)
            elif request_type == "seo":
                enhanced_message = self._enhance_seo_request(user_message, context)
            else:
                enhanced_message = user_message
            
            # Si necesita ayuda fiscal, solicitar a RAFAEL
            if needs_fiscal_help and self.zeus_core_ref:
                print(f"📡 [PERSEO] Detecté necesidad de ayuda fiscal, consultando a RAFAEL...")
                fiscal_response = self.request_agent_help(
                    "RAFAEL",
                    f"PERSEO necesita información fiscal para: {user_message}",
                    context
                )
                if fiscal_response and fiscal_response.get("success"):
                    enhanced_message += f"\n\n[Información de RAFAEL]: {fiscal_response.get('content', '')[:500]}"
            
            # Si necesita ayuda legal, solicitar a JUSTICIA
            if needs_legal_help and self.zeus_core_ref:
                print(f"📡 [PERSEO] Detecté necesidad de ayuda legal, consultando a JUSTICIA...")
                legal_response = self.request_agent_help(
                    "JUSTICIA",
                    f"PERSEO necesita información legal para: {user_message}",
                    context
                )
                if legal_response and legal_response.get("success"):
                    enhanced_message += f"\n\n[Información de JUSTICIA]: {legal_response.get('content', '')[:500]}"
        
        # Hacer decisión
        result = self.make_decision(enhanced_message, additional_context=context)
        
        # PERSEO-specific metadata
        result["domain"] = self.domain
        result["request_type"] = request_type
        
        return result
    
    def _enhance_campaign_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de campaña con contexto"""
        target_audience = context.get("target_audience", "no especificada")
        budget = context.get("budget", "no especificado")
        duration = context.get("duration", "no especificado")
        
        enhanced = f"""{message}

Contexto adicional:
- Audiencia objetivo: {target_audience}
- Presupuesto: {budget}
- Duración: {duration}

Por favor, proporciona:
1. Estrategia de canales (Google Ads, Facebook, Instagram, etc.)
2. Presupuesto recomendado por canal
3. KPIs a trackear
4. Cronograma de implementación
5. Métricas de éxito esperadas
"""
        return enhanced
    
    def _enhance_seo_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de SEO con contexto"""
        website = context.get("website", "no especificado")
        keywords = context.get("keywords", [])
        
        enhanced = f"""{message}

Contexto adicional:
- Website: {website}
- Keywords objetivo: {', '.join(keywords) if keywords else 'no especificadas'}

Por favor, proporciona:
1. Análisis de keywords actuales
2. Oportunidades de optimización
3. Estrategia de contenido
4. Recomendaciones técnicas (velocidad, mobile, estructura)
5. Timeline de implementación
"""
        return enhanced
    
    def check_hitl_required(self, decision: Dict) -> bool:
        """
        PERSEO requiere HITL para:
        - Campañas con presupuesto >1000€
        - Cambios en estrategia principal
        - Decisiones que afecten branding
        """
        # Check base
        if super().check_hitl_required(decision):
            return True
        
        content = decision.get("content", "").lower()
        
        # Detectar menciones de presupuesto alto
        budget_keywords = ["€", "euros", "presupuesto"]
        if any(kw in content for kw in budget_keywords):
            # Si menciona números >1000, requiere HITL
            import re
            numbers = re.findall(r'\d+', content)
            for num_str in numbers:
                if int(num_str) > 1000:
                    print(f"⚠️ [HITL] PERSEO: Presupuesto alto detectado (>{num_str})")
                    return True
        
        # Detectar cambios estratégicos
        strategic_keywords = ["rebranding", "cambio de estrategia", "nueva dirección", "pivote"]
        if any(kw in content for kw in strategic_keywords):
            print(f"⚠️ [HITL] PERSEO: Cambio estratégico detectado")
            return True
        
        return False

