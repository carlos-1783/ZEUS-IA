"""
⚡ THALOS - Defensor Cibernético ⚡
Agente especializado en Seguridad y Ciberdefensa
⚠️ CON SAFEGUARDS ESPECIALES PARA PROTEGER AL CREADOR
"""

import json
from typing import Dict, Any
from agents.base_agent import BaseAgent


class Thalos(BaseAgent):
    """
    THALOS - Escudo de Defensa Activa
    Especializado en seguridad cibernética y detección de amenazas
    
    ⚠️ SAFEGUARDS CRÍTICOS:
    - NUNCA puede aislar IPs del creador
    - NUNCA puede revocar credenciales de admin
    - Todas las acciones destructivas requieren aprobación humana explícita
    """
    
    # IPs protegidas del creador (whitelist inmutable)
    CREATOR_PROTECTED_IPS = [
        "127.0.0.1",
        "localhost",
        "::1"
        # Agregar IPs específicas del creador aquí
    ]
    
    # Usuarios protegidos (whitelist inmutable)
    PROTECTED_USERS = [
        "marketingdigitalper.seo@gmail.com",
        "admin",
        "root",
        "creator"
    ]
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        with open(prompts_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        thalos_config = config["zeus_prime_v1"]["agents"]["THALOS"]
        
        super().__init__(
            name="THALOS",
            role=thalos_config["role"],
            system_prompt=thalos_config["prompt"],
            temperature=thalos_config["parameters"]["temperature"],
            max_tokens=thalos_config["parameters"]["max_tokens"],
            hitl_threshold=0.95  # MUY alto para forzar aprobación humana
        )
        
        self.domain = thalos_config["parameters"]["domain"]
        self.auto_isolation = thalos_config["parameters"]["auto_isolation"]  # DEBE ser False
        self.critical_action_approval = thalos_config["parameters"]["critical_action_approval"]  # DEBE ser True
        
        # Validar safeguards
        if self.auto_isolation:
            raise ValueError("⚠️ CRITICAL: auto_isolation MUST be False for safety")
        if not self.critical_action_approval:
            raise ValueError("⚠️ CRITICAL: critical_action_approval MUST be True for safety")
        
        print(f"🛡️ THALOS inicializado - Dominio: {self.domain}")
        print(f"⚠️ SAFEGUARDS ACTIVOS: auto_isolation={self.auto_isolation}, approval_required={self.critical_action_approval}")
        print(f"🔒 PROTEGIDOS: {len(self.PROTECTED_USERS)} usuarios, {len(self.CREATOR_PROTECTED_IPS)} IPs")
    
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud de seguridad
        
        ⚠️ TODAS las acciones pasan por validación de safeguards
        """
        request_type = context.get("type", "general")
        user_message = context.get("message", context.get("user_message", ""))
        target_ip = context.get("target_ip")
        target_user = context.get("target_user")
        
        # Si es comunicación entre agentes, procesar directamente (pero mantener safeguards)
        is_inter_agent = context.get("inter_agent_communication", False)
        
        # SAFEGUARD 1: Verificar que no se ataque al creador
        if target_ip and self._is_protected_ip(target_ip):
            return {
                "status": "blocked",
                "reason": "🔒 IP protegida del creador - acción bloqueada por safeguards",
                "confidence": 1.0,
                "human_approval_required": True,
                "action_type": "PROTECTION_OVERRIDE_REQUIRED"
            }
        
        if target_user and self._is_protected_user(target_user):
            return {
                "status": "blocked",
                "reason": "🔒 Usuario protegido - acción bloqueada por safeguards",
                "confidence": 1.0,
                "human_approval_required": True,
                "action_type": "PROTECTION_OVERRIDE_REQUIRED"
            }
        
        # Enriquecer mensaje según tipo
        if request_type == "threat_detection":
            enhanced_message = self._enhance_threat_request(user_message, context)
        elif request_type == "incident_response":
            enhanced_message = self._enhance_incident_request(user_message, context)
        elif request_type == "audit":
            enhanced_message = self._enhance_audit_request(user_message, context)
        else:
            enhanced_message = user_message
        
        # Hacer decisión
        result = self.make_decision(enhanced_message, additional_context=context)
        
        # SAFEGUARD 2: Forzar aprobación humana para acciones críticas
        if self._is_critical_action(result):
            result["human_approval_required"] = True
            result["approval_reason"] = "Acción de seguridad crítica - requiere confirmación humana"
        
        # THALOS-specific metadata
        result["domain"] = self.domain
        result["request_type"] = request_type
        result["safeguards_checked"] = True
        
        return result
    
    def _is_protected_ip(self, ip: str) -> bool:
        """Verificar si IP está en whitelist de protección"""
        return ip in self.CREATOR_PROTECTED_IPS
    
    def _is_protected_user(self, user: str) -> bool:
        """Verificar si usuario está en whitelist de protección"""
        user_lower = user.lower()
        return any(protected.lower() in user_lower for protected in self.PROTECTED_USERS)
    
    def _is_critical_action(self, decision: Dict) -> bool:
        """
        Determinar si una acción es crítica y requiere aprobación
        
        Acciones críticas:
        - Aislar IPs
        - Revocar credenciales
        - Bloquear accesos
        - Modificar reglas de firewall
        - Cualquier acción destructiva
        """
        content = decision.get("content", "").lower()
        
        critical_keywords = [
            "aislar", "bloquear", "revocar", "eliminar", "denegar",
            "firewall", "ban", "blacklist", "desactivar", "suspender",
            "isolate", "block", "revoke", "deny", "disable"
        ]
        
        return any(kw in content for kw in critical_keywords)
    
    def _enhance_threat_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de detección de amenazas"""
        threat_score = context.get("threat_score", "unknown")
        source_ip = context.get("source_ip", "unknown")
        
        enhanced = f"""{message}

Contexto de amenaza:
- Threat Score: {threat_score}
- IP Origen: {source_ip}

⚠️ RECORDATORIO DE SAFEGUARDS:
- NO aislar IPs del creador ({', '.join(self.CREATOR_PROTECTED_IPS)})
- NO revocar credenciales de usuarios protegidos
- TODA acción destructiva requiere aprobación humana

Proporciona:
1. Análisis del nivel de amenaza (bajo/medio/alto/crítico)
2. Acciones recomendadas (observar/alertar/mitigar/bloquear)
3. Impacto estimado si no se actúa
4. Si requiere intervención humana inmediata
"""
        return enhanced
    
    def _enhance_incident_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de respuesta a incidentes"""
        incident_type = context.get("incident_type", "unknown")
        severity = context.get("severity", "unknown")
        
        enhanced = f"""{message}

Contexto del incidente:
- Tipo: {incident_type}
- Severidad: {severity}

⚠️ PROTOCOLOS DE SEGURIDAD:
- Verificar que NO afecta al creador antes de actuar
- Requerir aprobación para acciones irreversibles
- Documentar cada paso

Proporciona:
1. Plan de contención inmediata
2. Pasos de investigación
3. Estrategia de recuperación
4. Prevención futura
"""
        return enhanced
    
    def _enhance_audit_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de auditoría de seguridad"""
        audit_scope = context.get("scope", "full")
        
        enhanced = f"""{message}

Auditoría de seguridad:
- Alcance: {audit_scope}

Analiza:
1. Vulnerabilidades detectadas
2. Configuraciones inseguras
3. Accesos anómalos
4. Recomendaciones de mejora
5. Nivel de riesgo general
"""
        return enhanced
    
    def check_hitl_required(self, decision: Dict) -> bool:
        """
        THALOS requiere HITL para TODAS las acciones críticas
        """
        # Check base (threshold muy alto)
        if super().check_hitl_required(decision):
            return True
        
        # FORZAR HITL para acciones críticas
        if self._is_critical_action(decision):
            print(f"⚠️ [HITL] THALOS: Acción crítica detectada - requiere aprobación")
            return True
        
        return False

