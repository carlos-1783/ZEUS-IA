"""
⚡ ZEUS CORE - Orquestador Supremo ⚡
El cerebro central que coordina todos los agentes
"""

import json
from typing import Dict, List, Optional, Any
from agents.base_agent import BaseAgent


class ZeusCore(BaseAgent):
    """
    ZEUS CORE - Orquestador supremo del ecosistema
    Decide qué agente usar y coordina respuestas complejas
    """
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        with open(prompts_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        zeus_config = config["zeus_prime_v1"]["system"]
        
        super().__init__(
            name="ZEUS CORE",
            role=zeus_config["role"],
            system_prompt=zeus_config["prompt"],
            temperature=zeus_config["parameters"]["temperature"],
            max_tokens=zeus_config["parameters"]["max_tokens"]
        )
        
        # Agentes disponibles (se registrarán después)
        self.agents: Dict[str, BaseAgent] = {}
        
        print("⚡ ZEUS CORE inicializado - El Olimpo está listo ⚡")
    
    def register_agent(self, agent: BaseAgent):
        """Registrar un agente en el sistema"""
        self.agents[agent.name.upper()] = agent
        print(f"✅ [ZEUS] Agente {agent.name} registrado")
    
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud y decidir qué agente usar
        
        Args:
            context: {
                "user_message": "mensaje del usuario",
                "task_type": "marketing|fiscal|security|legal" (opcional)
            }
        
        Returns:
            Dict con respuesta del agente apropiado
        """
        user_message = context.get("user_message", "")
        task_type = context.get("task_type")
        
        # Si no se especifica tipo, ZEUS decide qué agente usar
        if not task_type:
            task_type = self._route_to_agent(user_message)
        
        # Mapear tipo a agente
        agent_mapping = {
            "marketing": "PERSEO",
            "fiscal": "RAFAEL",
            "security": "THALOS",
            "legal": "JUSTICIA"
        }
        
        agent_name = agent_mapping.get(task_type)
        
        if not agent_name or agent_name not in self.agents:
            # Si no hay agente disponible, ZEUS responde directamente
            return self._handle_directly(user_message)
        
        # Delegar al agente apropiado
        agent = self.agents[agent_name]
        print(f"🎯 [ZEUS] Delegando a {agent_name}...")
        
        result = agent.make_decision(user_message, additional_context=context)
        
        # ZEUS agrega metadata de orquestación
        result["routed_by"] = "ZEUS CORE"
        result["selected_agent"] = agent_name
        
        return result
    
    def _route_to_agent(self, user_message: str) -> str:
        """
        Decidir qué agente debe manejar la solicitud
        (Heurística simple por ahora, se puede mejorar con embedding search)
        """
        message_lower = user_message.lower()
        
        # Keywords para cada agente
        marketing_keywords = [
            "marketing", "campaña", "anuncio", "seo", "sem", "ventas", 
            "cliente", "lead", "conversión", "tráfico", "contenido",
            "redes sociales", "instagram", "facebook", "google ads"
        ]
        
        fiscal_keywords = [
            "factura", "impuesto", "iva", "irpf", "modelo", "hacienda",
            "contable", "gasto", "ingreso", "deducible", "declaración",
            "fiscal", "tributario", "gastos", "ingresos"
        ]
        
        security_keywords = [
            "seguridad", "ataque", "amenaza", "vulnerabilidad", "hackeo",
            "ip", "firewall", "log", "incidente", "malware", "ransomware"
        ]
        
        legal_keywords = [
            "legal", "contrato", "gdpr", "privacidad", "datos personales",
            "consentimiento", "política", "términos", "condiciones", "ley"
        ]
        
        # Contar matches
        scores = {
            "marketing": sum(1 for kw in marketing_keywords if kw in message_lower),
            "fiscal": sum(1 for kw in fiscal_keywords if kw in message_lower),
            "security": sum(1 for kw in security_keywords if kw in message_lower),
            "legal": sum(1 for kw in legal_keywords if kw in message_lower)
        }
        
        # Seleccionar el que tenga más matches
        selected_type = max(scores, key=scores.get)
        
        if scores[selected_type] == 0:
            # Si no hay matches, default a marketing (PERSEO)
            selected_type = "marketing"
        
        print(f"🧠 [ZEUS] Routing scores: {scores} → {selected_type}")
        
        return selected_type
    
    def _handle_directly(self, user_message: str) -> Dict[str, Any]:
        """ZEUS maneja la solicitud directamente (cuando no hay agente apropiado)"""
        print("🏛️ [ZEUS] Manejando solicitud directamente")
        
        result = self.make_decision(user_message)
        result["routed_by"] = "ZEUS CORE"
        result["selected_agent"] = "ZEUS CORE (directo)"
        
        return result
    
    def get_system_status(self) -> Dict[str, Any]:
        """Obtener estado de todo el sistema"""
        return {
            "zeus_core": self.get_stats(),
            "agents": {
                name: agent.get_stats()
                for name, agent in self.agents.items()
            },
            "total_agents": len(self.agents),
            "system_status": "online" if self.is_active else "offline"
        }

