"""
⚡ ZEUS CORE - Orquestador Supremo ⚡
El cerebro central que coordina todos los agentes
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from agents.base_agent import BaseAgent
from services.activity_logger import activity_logger

if TYPE_CHECKING:
    from services.teamflow_engine import TeamFlowEngine


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
        
        # Cargar configuración de comportamiento y orquestación
        zeus_core_config_path = os.path.join(base_dir, "config", "zeus_core_config.json")
        try:
            with open(zeus_core_config_path, "r", encoding="utf-8") as f:
                self.orchestration_config = json.load(f)
            print("⚙️ [ZEUS] Configuración de orquestación cargada")
        except FileNotFoundError:
            print("⚠️ [ZEUS] Configuración de orquestación no encontrada, usando defaults")
            self.orchestration_config = {
                "project_state_engine": {"default_state": "PRE_LAUNCH", "allowed_states": []},
                "behavior_rules": {},
                "context_inference": {},
                "prelaunch_execution_flow": [],
                "response_templates": {}
            }
        
        # Agentes disponibles (se registrarán después)
        self.agents: Dict[str, BaseAgent] = {}
        self.prelaunch_active = False
        self.prelaunch_plan: Optional[Dict[str, Any]] = None
        self.project_state = self.orchestration_config.get("project_state_engine", {}).get("default_state", "PRE_LAUNCH")
        self.teamflow_engine: Optional["TeamFlowEngine"] = None
        self.shared_context: Dict[str, Dict[str, Any]] = {}
        self.execution_snapshots: List[Dict[str, Any]] = []
        
        print("⚡ ZEUS CORE inicializado - El Olimpo está listo ⚡")
    
    def register_agent(self, agent: BaseAgent):
        """Registrar un agente en el sistema"""
        self.agents[agent.name.upper()] = agent
        print(f"✅ [ZEUS] Agente {agent.name} registrado")

    def set_teamflow_engine(self, engine: "TeamFlowEngine"):
        """Asociar el motor TeamFlow para coordinación avanzada."""
        self.teamflow_engine = engine
        print("🧠 [ZEUS] Motor TeamFlow conectado")
    
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
        self.shared_context[agent_name] = result
        
        # ZEUS agrega metadata de orquestación
        result["routed_by"] = "ZEUS CORE"
        result["selected_agent"] = agent_name
        result.setdefault("metadata", {})
        result["metadata"]["decision_metadata"] = self._build_decision_metadata(
            agent_name=agent_name,
            task_type=task_type,
            context=context,
        )

        if context.get("workflow_id"):
            result["metadata"]["workflow"] = {
                "id": context["workflow_id"],
                "origin": "TeamFlow",
            }
        
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
    
    def communicate_between_agents(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Permitir que un agente se comunique con otro agente
        
        Args:
            from_agent: Nombre del agente que envía el mensaje
            to_agent: Nombre del agente destinatario
            message: Mensaje a enviar
            context: Contexto adicional opcional
        
        Returns:
            Dict con respuesta del agente destinatario
        """
        from_agent_upper = from_agent.upper()
        to_agent_upper = to_agent.upper()
        
        if from_agent_upper not in self.agents:
            return {
                "success": False,
                "error": f"Agente origen '{from_agent}' no encontrado"
            }
        
        if to_agent_upper not in self.agents:
            return {
                "success": False,
                "error": f"Agente destino '{to_agent}' no encontrado"
            }
        
        print(f"📡 [ZEUS] {from_agent_upper} → {to_agent_upper}: {message[:100]}...")
        
        # Preparar contexto para el agente destinatario
        agent_context = {
            "user_message": message,
            "from_agent": from_agent_upper,
            "inter_agent_communication": True,
            **(context or {})
        }
        if self.shared_context.get(from_agent_upper):
            agent_context.setdefault("shared_context", {})
            agent_context["shared_context"][from_agent_upper] = self.shared_context[from_agent_upper]
        
        # Obtener respuesta del agente destinatario
        target_agent = self.agents[to_agent_upper]
        result = target_agent.process_request(agent_context)
        self.shared_context[to_agent_upper] = result
        
        # Agregar metadata de comunicación
        result["communication_metadata"] = {
            "from": from_agent_upper,
            "to": to_agent_upper,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"✅ [ZEUS] {to_agent_upper} respondió a {from_agent_upper}")
        
        return result
    
    def coordinate_multi_agent_task(
        self,
        task_description: str,
        required_agents: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Coordinar una tarea que requiere múltiples agentes
        
        Args:
            task_description: Descripción de la tarea
            required_agents: Lista de agentes necesarios
            context: Contexto adicional
        
        Returns:
            Dict con resultados de todos los agentes
        """
        print(f"🎯 [ZEUS] Coordinando tarea multi-agente: {task_description}")

        teamflow_run = None
        if context and context.get("workflow_id") and self.teamflow_engine:
            try:
                teamflow_run = self.teamflow_engine.run_workflow(
                    workflow_id=context["workflow_id"],
                    payload=context.get("workflow_payload"),
                    actor=context.get("requested_by"),
                )
                self.execution_snapshots.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "workflow": context["workflow_id"],
                        "execution_id": teamflow_run["execution_id"],
                        "summary": task_description,
                    }
                )
            except ValueError as exc:
                print(f"⚠️ [ZEUS] Error iniciando TeamFlow: {exc}")
        
        results = {}
        for agent_name in required_agents:
            agent_upper = agent_name.upper()
            if agent_upper not in self.agents:
                results[agent_upper] = {
                    "success": False,
                    "error": f"Agente '{agent_name}' no disponible"
                }
                continue
            
            agent = self.agents[agent_upper]
            agent_context = {
                "user_message": task_description,
                "multi_agent_task": True,
                "other_agents": [a for a in required_agents if a.upper() != agent_upper],
                **(context or {})
            }
            
            result = agent.process_request(agent_context)
            results[agent_upper] = result
        
        return {
            "success": True,
            "task": task_description,
            "agents_involved": required_agents,
            "results": results,
            "coordinated_by": "ZEUS CORE",
            "teamflow_execution": teamflow_run
        }

    def _build_decision_metadata(self, agent_name: str, task_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Crear metadata trazable para auditoría y paneles."""
        return {
            "agent": agent_name,
            "task_type": task_type,
            "phase": context.get("phase", "general"),
            "workflow_id": context.get("workflow_id"),
            "scores": context.get("routing_scores"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_execution_panel(self) -> Dict[str, Any]:
        """Panel resumido de ejecuciones y validaciones."""
        last_runs = self.execution_snapshots[-5:]
        teamflow_status = (
            self.teamflow_engine.validate_integrations()
            if self.teamflow_engine
            else {"status": "offline"}
        )
        return {
            "recent_executions": last_runs,
            "teamflow_status": teamflow_status,
            "agents_online": len(self.agents),
        }

    # ============================================================
    # Planificación estratégica
    # ============================================================

    def _start_prelaunch_phase(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Iniciar fase de pre-lanzamiento usando configuración de orquestación.
        Sigue el flujo definido en zeus_core_config.json: AUTO_DETECT -> PROPOSE -> CONFIRM -> BUILD
        """
        # Aplicar reglas de comportamiento para PRE_LAUNCH
        behavior_rules = self.orchestration_config.get("behavior_rules", {}).get("PRE_LAUNCH", {})
        interaction_mode = behavior_rules.get("interaction_mode", "GUIDED_PROACTIVE")
        question_policy = behavior_rules.get("question_policy", "CONFIRM_ONLY")
        
        # Paso 1: AUTO_DETECT_PROJECT (inferir contexto)
        detected_scenario = self._auto_detect_project(context)
        
        # Paso 2: PROPOSE_STRATEGY (proponer plan)
        proposed_strategy = self._propose_prelaunch_strategy(detected_scenario, context)
        
        # Si no está activo, crear el plan completo
        if not self.prelaunch_active:
            plan = self._build_prelaunch_plan()
            self._register_prelaunch_tasks(plan)
            self.prelaunch_active = True
            self.project_state = "PRE_LAUNCH"
            tasks_created = True
            self.prelaunch_plan = plan
        else:
            print("ℹ️ [ZEUS] Fase PRE-LANZAMIENTO ya estaba activa. Se entrega resumen actualizado.")
            plan = self.prelaunch_plan or self._build_prelaunch_plan()
            tasks_created = False

        # Paso 3: CONFIRMATION_REQUEST (usar plantillas de respuesta)
        response_templates = self.orchestration_config.get("response_templates", {})
        intro_text = response_templates.get(
            "prelaunch_intro", 
            "Detecto que estás en fase de pre-lanzamiento. Basándome en ZEUS, propongo este escenario inicial."
        )
        confirmation_prompt = response_templates.get(
            "confirmation_prompt",
            "¿Confirmamos este escenario o ajustamos algo mínimo?"
        )
        
        summary_text = self._render_prelaunch_summary(plan, tasks_created=tasks_created)
        full_content = f"{intro_text}\n\n{summary_text}\n\n{confirmation_prompt}"

        return {
            "success": True,
            "agent": self.name,
            "role": self.role,
            "content": full_content,
            "confidence": 0.92,
            "hitl_required": False,
            "human_approval_required": question_policy == "CONFIRM_ONLY",
            "plan": plan,
            "tasks_created": tasks_created,
            "detected_scenario": detected_scenario,
            "proposed_strategy": proposed_strategy,
            "project_state": self.project_state,
            "interaction_mode": interaction_mode
        }
    
    def _auto_detect_project(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Paso 1: Auto-detectar el proyecto basado en contexto y configuración"""
        inference_config = self.orchestration_config.get("context_inference", {})
        assumptions = inference_config.get("assumptions_if_missing", {})
        
        # Intentar inferir desde datos internos de ZEUS
        detected = {
            "product_type": assumptions.get("product_type", "Plataforma IA empresarial"),
            "market": assumptions.get("market", "B2B"),
            "goal": assumptions.get("goal", "Validación + captación de leads"),
            "channels": assumptions.get("channels", ["LinkedIn", "Email", "WhatsApp Business"]),
            "source": "ZEUS_INTERNAL_DATA"
        }
        
        # Si hay contexto del usuario, intentar mejorar la inferencia
        if context.get("user_message"):
            user_msg = context["user_message"].lower()
            # Detectar keywords para ajustar inferencias
            if "saas" in user_msg or "software" in user_msg:
                detected["product_type"] = "SaaS"
            if "b2c" in user_msg or "consumidor" in user_msg:
                detected["market"] = "B2C"
        
        print(f"🔍 [ZEUS] Proyecto detectado: {detected['product_type']} - {detected['market']}")
        return detected
    
    def _propose_prelaunch_strategy(self, scenario: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Paso 2: Proponer estrategia basada en escenario detectado"""
        execution_flow = self.orchestration_config.get("prelaunch_execution_flow", [])
        
        strategy = {
            "value_proposition": f"Lanzamiento de {scenario['product_type']} en mercado {scenario['market']}",
            "main_message": f"Posicionar {scenario['product_type']} como solución líder",
            "channels": scenario.get("channels", []),
            "timing": {
                "7_days": "Setup inicial y configuración",
                "14_days": "Primeras campañas y validación",
                "30_days": "Escalado y optimización"
            }
        }
        
        print(f"💡 [ZEUS] Estrategia propuesta para {scenario['product_type']}")
        return strategy

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

    # ============================================================
    # APIs públicas para orquestación
    # ============================================================

    def ensure_prelaunch_plan(self) -> Dict[str, Any]:
        """
        Garantizar que el plan de pre-lanzamiento esté generado y registrado.
        Útil para inicializar tareas automáticamente en el arranque del sistema.
        """
        if self.prelaunch_active and self.prelaunch_plan:
            return {
                "success": True,
                "already_active": True,
                "plan": self.prelaunch_plan
            }

        result = self._start_prelaunch_phase({"phase": "prelaunch", "origin": "auto-init"})
        self.prelaunch_plan = result.get("plan")
        self.prelaunch_active = True
        return result

    # ============================================================
    # APIs públicas para orquestación
    # ============================================================

    def ensure_prelaunch_plan(self) -> Dict[str, Any]:
        """
        Garantizar que el plan de pre-lanzamiento está generado.
        Se usa en el arranque para poblar actividades aunque
        ningún usuario haya enviado todavía el prompt maestro.
        """
        if self.prelaunch_active and self.prelaunch_plan:
            return {
                "success": True,
                "already_active": True,
                "plan": self.prelaunch_plan
            }
        
        result = self._start_prelaunch_phase({"phase": "prelaunch", "origin": "auto-init"})
        self.prelaunch_plan = result.get("plan")
        return result

