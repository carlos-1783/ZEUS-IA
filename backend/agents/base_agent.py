"""
⚡ ZEUS-IA Base Agent ⚡
Clase base para todos los agentes
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from abc import ABC, abstractmethod

from services.openai_service import chat_completion, parse_json_response
from config.settings import settings


class BaseAgent(ABC):
    """Clase base para todos los agentes de ZEUS"""
    
    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        hitl_threshold: float = 0.75
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.hitl_threshold = hitl_threshold
        
        # State
        self.is_active = True
        self.total_requests = 0
        self.total_cost = 0.0
        self.last_request_time = None
        self.zeus_core_ref = None  # Referencia a ZEUS CORE para comunicación entre agentes
        
        print(f"🏛️ [ZEUS] Agente {self.name} ({self.role}) inicializado")
    
    def set_zeus_core_ref(self, zeus_core):
        """Establecer referencia a ZEUS CORE para comunicación entre agentes"""
        self.zeus_core_ref = zeus_core
    
    def request_agent_help(self, target_agent: str, question: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Solicitar ayuda a otro agente a través de ZEUS CORE
        
        Args:
            target_agent: Nombre del agente al que solicitar ayuda
            question: Pregunta o solicitud
            context: Contexto adicional
        
        Returns:
            Dict con respuesta del agente o None si no hay comunicación disponible
        """
        if not self.zeus_core_ref:
            print(f"⚠️ [{self.name}] No hay referencia a ZEUS CORE para comunicación")
            return None
        
        print(f"📡 [{self.name}] Solicitando ayuda a {target_agent}: {question[:100]}...")
        
        result = self.zeus_core_ref.communicate_between_agents(
            from_agent=self.name,
            to_agent=target_agent,
            message=question,
            context=context
        )
        
        return result
    
    @abstractmethod
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud (debe ser implementado por cada agente)
        
        Args:
            context: Contexto de la solicitud
        
        Returns:
            Dict con resultado de la decisión
        """
        pass
    
    def make_decision(self, user_message: str, additional_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Tomar decisión usando OpenAI.
        Usa conversation_history / _memory.short_term si existe (unified runtime).
        """
        self.total_requests += 1
        self.last_request_time = datetime.now()

        messages = [{"role": "system", "content": self.system_prompt}]
        history = []
        if additional_context:
            hist = additional_context.get("conversation_history")
            if hist is None and isinstance(additional_context.get("_memory"), dict):
                hist = additional_context["_memory"].get("short_term")
            if isinstance(hist, list) and hist:
                for m in hist:
                    if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
                        history.append({"role": m["role"], "content": m["content"]})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        if additional_context:
            skip = {"conversation_history", "_memory", "user_message"}
            extra = {k: v for k, v in additional_context.items() if k not in skip and not k.startswith("_")}
            if extra:
                context_str = f"\n\nContexto adicional:\n{json.dumps(extra, indent=2, ensure_ascii=False)}"
                messages[-1]["content"] = messages[-1]["content"] + context_str
        
        # Llamar a OpenAI
        response = chat_completion(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        if not response["success"]:
            return {
                "success": False,
                "error": response["error"],
                "agent": self.name,
                "timestamp": response["timestamp"]
            }
        
        # Actualizar costos
        self.total_cost += response["cost"]
        
        # Construir respuesta
        result = {
            "success": True,
            "agent": self.name,
            "role": self.role,
            "content": response["content"],
            "confidence": self._calculate_confidence(response),
            "hitl_required": False,  # Se calcula después
            "reasoning": self._extract_reasoning(response["content"]),
            "metadata": {
                "model": response["model"],
                "tokens": response["usage"]["total_tokens"],
                "cost": response["cost"],
                "elapsed_time": response["elapsed_time"],
                "timestamp": response["timestamp"]
            }
        }
        
        # Verificar si requiere HITL
        result["hitl_required"] = self.check_hitl_required(result)
        
        return result
    
    def _calculate_confidence(self, response: Dict) -> float:
        """
        Calcular confianza de la respuesta
        (Heurística simple por ahora, se puede mejorar)
        """
        content = response.get("content", "")
        
        # Indicadores de alta confianza
        high_confidence_keywords = ["definitivamente", "claramente", "sin duda", "ciertamente", "seguro"]
        
        # Indicadores de baja confianza
        low_confidence_keywords = ["quizás", "tal vez", "posiblemente", "podría", "no estoy seguro", "depende"]
        
        confidence = 0.8  # Default
        
        content_lower = content.lower()
        
        for keyword in high_confidence_keywords:
            if keyword in content_lower:
                confidence = min(0.95, confidence + 0.05)
        
        for keyword in low_confidence_keywords:
            if keyword in content_lower:
                confidence = max(0.4, confidence - 0.15)
        
        return round(confidence, 2)
    
    def _extract_reasoning(self, content: str) -> str:
        """
        Extraer razonamiento de la respuesta
        (Intenta identificar la parte que explica el por qué)
        """
        # Si la respuesta es JSON, intentar extraer el campo "reasoning"
        json_data = parse_json_response(content)
        if json_data and "reasoning" in json_data:
            return json_data["reasoning"]
        
        # Si es texto plano, buscar patrones de razonamiento
        reasoning_markers = [
            "porque", "debido a", "razón:", "razonamiento:",
            "esto se debe", "considerando que", "dado que"
        ]
        
        for marker in reasoning_markers:
            if marker in content.lower():
                # Extraer desde el marcador hasta el final o el siguiente punto
                start = content.lower().find(marker)
                end = content.find(".", start + 50)
                if end == -1:
                    end = len(content)
                return content[start:end].strip()
        
        # Si no se encuentra, devolver las primeras 200 chars
        return content[:200] + ("..." if len(content) > 200 else "")
    
    def check_hitl_required(self, decision: Dict) -> bool:
        """
        Verificar si la decisión requiere aprobación humana (HITL)
        
        Args:
            decision: Decisión tomada
        
        Returns:
            True si requiere HITL, False si no
        """
        if not settings.HITL_ENABLED:
            return False
        
        # Regla 1: Confianza baja
        if decision.get("confidence", 1.0) < self.hitl_threshold:
            print(f"⚠️ [HITL] {self.name}: Confianza baja ({decision.get('confidence')})")
            return True
        
        # Regla 2: Palabras clave que indican incertidumbre
        content = decision.get("content", "").lower()
        uncertain_keywords = ["no estoy seguro", "necesito más información", "requiere revisión"]
        
        for keyword in uncertain_keywords:
            if keyword in content:
                print(f"⚠️ [HITL] {self.name}: Palabra clave de incertidumbre detectada")
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del agente"""
        return {
            "name": self.name,
            "role": self.role,
            "is_active": self.is_active,
            "total_requests": self.total_requests,
            "total_cost": round(self.total_cost, 4),
            "last_request": self.last_request_time.isoformat() if self.last_request_time else None,
            "hitl_threshold": self.hitl_threshold
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} role={self.role}>"

