"""
⚡ ZEUS CORE - Orquestador Supremo ⚡
El cerebro central que coordina todos los agentes
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from agents.base_agent import BaseAgent
from services.activity_logger import activity_logger


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
        self.prelaunch_active = False
        
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
        message_lower = user_message.lower()
        
        # Detectar activación de planes especiales
        if (
            "pre-lanzamiento" in message_lower
            or "pre lanzamiento" in message_lower
            or context.get("phase") == "prelaunch"
        ):
            return self._start_prelaunch_phase(context)
        
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

    # ============================================================
    # Planificación estratégica
    # ============================================================

    def _start_prelaunch_phase(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Iniciar fase de pre-lanzamiento con cronograma y tareas asignadas.
        """
        plan = self._build_prelaunch_plan()
        tasks_created = False

        if not self.prelaunch_active:
            self._register_prelaunch_tasks(plan)
            self.prelaunch_active = True
            tasks_created = True
        else:
            print("ℹ️ [ZEUS] Fase PRE-LANZAMIENTO ya estaba activa. Se entrega resumen actualizado.")

        summary_text = self._render_prelaunch_summary(plan, tasks_created=tasks_created)

        return {
            "success": True,
            "agent": self.name,
            "role": self.role,
            "content": summary_text,
            "confidence": 0.92,
            "hitl_required": False,
            "human_approval_required": False,
            "plan": plan,
            "tasks_created": tasks_created
        }

    def _build_prelaunch_plan(self) -> Dict[str, Any]:
        """Construir cronograma y responsabilidades para la fase de pre-lanzamiento."""
        today = datetime.utcnow().date()

        timeline = [
            {
                "week": 1,
                "focus": "Diagnóstico y cimientos",
                "window": f"{today} → {today + timedelta(days=6)}",
                "milestones": [
                    "Inventario de credenciales y accesos",
                    "Plan de marketing 360° aprobado",
                    "Checklist legal y fiscal preliminar"
                ]
            },
            {
                "week": 2,
                "focus": "Producción y automatizaciones",
                "window": f"{today + timedelta(days=7)} → {today + timedelta(days=13)}",
                "milestones": [
                    "Campañas configuradas en modo simulación",
                    "Playbooks operativos completados",
                    "Alertas de seguridad activas"
                ]
            },
            {
                "week": 3,
                "focus": "Go-Live y soporte inicial",
                "window": f"{today + timedelta(days=14)} → {today + timedelta(days=20)}",
                "milestones": [
                    "Checklist final de lanzamiento",
                    "Plan de soporte 24/7 operativo",
                    "Kit de bienvenida para clientes listo"
                ]
            }
        ]

        tasks = [
            # PERSEO
            {
                "agent": "PERSEO",
                "week": 1,
                "action_type": "task_assigned",
                "description": "Diseñar plan de marketing 360° con escenarios real y simulación.",
                "priority": "high",
                "due_in_days": 3
            },
            {
                "agent": "PERSEO",
                "week": 2,
                "action_type": "task_assigned",
                "description": "Configurar campañas en Meta y Google en modo simulación y preparar assets finales.",
                "priority": "high",
                "due_in_days": 10
            },
            {
                "agent": "PERSEO",
                "week": 3,
                "action_type": "task_assigned",
                "description": "Preparar playbook de activación inmediata cuando lleguen los tokens pendientes.",
                "priority": "medium",
                "due_in_days": 18
            },
            # RAFAEL
            {
                "agent": "RAFAEL",
                "week": 1,
                "action_type": "task_assigned",
                "description": "Inventariar modelos fiscales necesarios y mapear documentación requerida.",
                "priority": "medium",
                "due_in_days": 4
            },
            {
                "agent": "RAFAEL",
                "week": 2,
                "action_type": "task_assigned",
                "description": "Crear plantillas de facturación y modelos SII con datos ficticios.",
                "priority": "medium",
                "due_in_days": 11
            },
            {
                "agent": "RAFAEL",
                "week": 3,
                "action_type": "task_assigned",
                "description": "Manual operativo de lanzamientos fiscales y gestión de cobros híbridos.",
                "priority": "high",
                "due_in_days": 19
            },
            # THALOS
            {
                "agent": "THALOS",
                "week": 1,
                "action_type": "security_scan",
                "description": "Auditoría de credenciales Railway y servicios externos + informe de riesgos.",
                "priority": "critical",
                "due_in_days": 5
            },
            {
                "agent": "THALOS",
                "week": 2,
                "action_type": "task_assigned",
                "description": "Configurar alertas de seguridad y monitoreo continuo (logs, tokens, accesos).",
                "priority": "high",
                "due_in_days": 12
            },
            {
                "agent": "THALOS",
                "week": 3,
                "action_type": "backup_created",
                "description": "Plan de recuperación ante desastres y pruebas de backups previas al lanzamiento.",
                "priority": "high",
                "due_in_days": 19
            },
            # JUSTICIA
            {
                "agent": "JUSTICIA",
                "week": 1,
                "action_type": "document_reviewed",
                "description": "Actualizar política de privacidad, términos y acuerdos de confidencialidad.",
                "priority": "high",
                "due_in_days": 4
            },
            {
                "agent": "JUSTICIA",
                "week": 2,
                "action_type": "compliance_check",
                "description": "Checklist de cumplimiento para integraciones LinkedIn/TikTok y RGPD.",
                "priority": "medium",
                "due_in_days": 11
            },
            {
                "agent": "JUSTICIA",
                "week": 3,
                "action_type": "task_assigned",
                "description": "Kit legal de lanzamiento: contratos de servicio, anexos y disclaimers finales.",
                "priority": "high",
                "due_in_days": 18
            },
            # AFRODITA
            {
                "agent": "AFRODITA",
                "week": 1,
                "action_type": "task_assigned",
                "description": "Definir estructura de soporte y roles para primeras 4 semanas post-lanzamiento.",
                "priority": "medium",
                "due_in_days": 6
            },
            {
                "agent": "AFRODITA",
                "week": 2,
                "action_type": "task_assigned",
                "description": "Manual de onboarding interno y de clientes, incluyendo flujos de comunicación.",
                "priority": "medium",
                "due_in_days": 12
            },
            {
                "agent": "AFRODITA",
                "week": 3,
                "action_type": "task_assigned",
                "description": "Calendarizar reuniones de soporte y coordinación con RAFAEL para cobros.",
                "priority": "medium",
                "due_in_days": 19
            }
        ]

        reporting = {
            "daily_flash": "Informe flash diario: tareas completadas, bloqueos y novedades en credenciales.",
            "weekly_review": "Revisión semanal cruzada con checklist de readiness.",
            "alerts": "Escalada automática a Carlos si un bloqueo supera las 24h."
        }

        return {
            "timeline": timeline,
            "tasks": tasks,
            "reporting": reporting,
            "phase": "pre-launch"
        }

    def _register_prelaunch_tasks(self, plan: Dict[str, Any]) -> None:
        """Registrar tareas en el Activity Logger."""
        now = datetime.utcnow()

        # Registrar coordinación general de ZEUS
        activity_logger.log_activity(
            agent_name=self._normalize_agent_name(self.name),
            action_type="coordination",
            action_description="Fase PRE-LANZAMIENTO activada y plan maestro distribuido.",
            details={
                "phase": plan["phase"],
                "timeline": plan["timeline"],
                "reporting": plan["reporting"],
                "activated_at": now.isoformat()
            },
            status="in_progress",
            priority="high"
        )

        for task in plan["tasks"]:
            due_date = (now + timedelta(days=task["due_in_days"])).isoformat()
            activity_logger.log_activity(
                agent_name=self._normalize_agent_name(task["agent"]),
                action_type=task["action_type"],
                action_description=task["description"],
                details={
                    "phase": plan["phase"],
                    "week": task["week"],
                    "due_date": due_date,
                    "assigned_by": "ZEUS CORE"
                },
                status="pending",
                priority=task["priority"],
                visible_to_client=True
            )

    def _render_prelaunch_summary(self, plan: Dict[str, Any], tasks_created: bool) -> str:
        """Generar resumen textual para el usuario."""
        created_text = "✅ Tareas registradas en el panel de actividad." if tasks_created else "ℹ️ Tareas ya estaban registradas; se mantiene el plan."

        timeline_lines = []
        for block in plan["timeline"]:
            milestones = "; ".join(block["milestones"])
            timeline_lines.append(f"- Semana {block['week']} ({block['window']}): {block['focus']} → {milestones}")

        summary = [
            "### Fase PRE-LANZAMIENTO activada",
            created_text,
            "",
            "**Cronograma:**",
            *timeline_lines,
            "",
            "**Reportes:**",
            f"- Diario: {plan['reporting']['daily_flash']}",
            f"- Semanal: {plan['reporting']['weekly_review']}",
            f"- Alertas: {plan['reporting']['alerts']}",
            "",
            "Si llega alguna credencial pendiente, actualizo automáticamente el plan y notifico en el informe diario."
        ]

        return "\n".join(summary)

    @staticmethod
    def _normalize_agent_name(name: str) -> str:
        """Normalizar nombre de agente para registros (sin espacios, mayúsculas)."""
        if not name:
            return "ZEUS"
        return name.strip().split(" ")[0].upper()

