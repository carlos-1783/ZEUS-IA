"""
🧠 TeamFlow Engine
Coordinador de workflows multiagente para ZEUS IA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.activity_logger import ActivityLogger


@dataclass
class TeamFlowStep:
    """Representa un paso dentro de un workflow."""

    id: str
    name: str
    agent: str
    action_type: str
    description: str
    expected_output: str
    depends_on: List[str] = field(default_factory=list)
    handoff_to: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamFlowWorkflow:
    """Definición de un workflow TeamFlow."""

    workflow_id: str
    title: str
    summary: str
    category: str
    success_criteria: List[str]
    steps: List[TeamFlowStep]
    entry_conditions: List[str]
    default_payload: Dict[str, Any]
    sla_minutes: int = 30

    @property
    def agents(self) -> List[str]:
        return sorted({step.agent for step in self.steps})


def _build_workflows() -> Dict[str, TeamFlowWorkflow]:
    """Inicializa la librería de workflows solicitados."""

    def step(**kwargs: Any) -> TeamFlowStep:
        return TeamFlowStep(**kwargs)

    workflows: List[TeamFlowWorkflow] = [
        TeamFlowWorkflow(
            workflow_id="prelaunch_campaign_v1",
            title="Pre-Launch Campaign 360º",
            category="marketing",
            summary="Activa assets de lanzamiento coordinando marketing, legal y seguridad.",
            success_criteria=[
                "Creatividades aprobadas",
                "Contratos validados por JUSTICIA",
                "Alertas de seguridad habilitadas por THALOS",
            ],
            entry_conditions=[
                "Credenciales mínimas en Stripe/Google",
                "Activos base cargados en PERSEO",
                "Checklist legal preliminar cargado",
            ],
            default_payload={
                "brand": "ZEUS IA",
                "launch_window": "inmediato",
                "budget_mode": "sandbox",
            },
            sla_minutes=90,
            steps=[
                step(
                    id="marketing_brief",
                    name="Brief creativo y assets",
                    agent="PERSEO",
                    action_type="task_assigned",
                    description="Generar plan creativo multiformato y prompts IA",
                    expected_output="Entregable con guion, prompts y assets recomendados",
                    handoff_to=["legal_review", "security_scan"],
                ),
                step(
                    id="legal_review",
                    name="Revisión legal express",
                    agent="JUSTICIA",
                    action_type="document_reviewed",
                    description="Validar disclaimers, contratos y permisos de uso",
                    depends_on=["marketing_brief"],
                    expected_output="Checklist legal con estado y observaciones",
                    handoff_to=["security_scan"],
                ),
                step(
                    id="security_scan",
                    name="Chequeo de seguridad CORS/API",
                    agent="THALOS",
                    action_type="security_scan",
                    description="Validar CORS, tokens y acceso a uploads antes de lanzar",
                    depends_on=["marketing_brief"],
                    expected_output="Informe de riesgos + plan de mitigación",
                    handoff_to=["ads_go_live"],
                ),
                step(
                    id="ads_go_live",
                    name="Checklist final y go-live",
                    agent="ZEUS CORE",
                    action_type="coordination",
                    description="Consolidar métricas y aprobar lanzamiento",
                    depends_on=["legal_review", "security_scan"],
                    expected_output="Acta de activación con métricas iniciales",
                ),
            ],
        ),
        TeamFlowWorkflow(
            workflow_id="invoice_flow_v1",
            title="Factura y conciliación automática",
            category="finanzas",
            summary="Flujo completo de facturación con QR/NFC y validaciones fiscales.",
            success_criteria=[
                "Factura emitida",
                "QR generado",
                "Integración con Hacienda preparada",
            ],
            entry_conditions=["Cliente con datos completos", "Precio definido"],
            default_payload={"currency": "EUR", "tax_rate": 21},
            steps=[
                step(
                    id="qr_capture",
                    name="Captura QR/NFC",
                    agent="RAFAEL",
                    action_type="task_assigned",
                    description="Leer QR o NFC para pre-rellenar factura.",
                    expected_output="Payload estructurado con datos fiscales",
                    handoff_to=["invoice_generation"],
                ),
                step(
                    id="invoice_generation",
                    name="Generar factura",
                    agent="RAFAEL",
                    action_type="invoice_sent",
                    description="Construir factura + modelo 303/390 asociado.",
                    depends_on=["qr_capture"],
                    expected_output="Factura y modelos listos para presentar",
                    handoff_to=["legal_stamp"],
                ),
                step(
                    id="legal_stamp",
                    name="Firma y archivo legal",
                    agent="JUSTICIA",
                    action_type="document_reviewed",
                    description="Firmar digitalmente PDF y archivar en expediente legal.",
                    depends_on=["invoice_generation"],
                    expected_output="PDF firmado + hash auditado",
                ),
            ],
        ),
        TeamFlowWorkflow(
            workflow_id="contract_sign_v1",
            title="Generación y firma de contratos publicitarios",
            category="legal",
            summary="Coordina a JUSTICIA y PERSEO para contratos de media/ads.",
            success_criteria=[
                "Contrato personalizado generado",
                "Firma digital y registro GDPR",
            ],
            entry_conditions=["Brief comercial", "Datos de cliente"],
            default_payload={"jurisdiction": "ES"},
            steps=[
                step(
                    id="contract_blueprint",
                    name="Plantilla personalizada",
                    agent="JUSTICIA",
                    action_type="contract_generator",
                    description="Generar contrato adaptado a campaña publicitaria.",
                    expected_output="Contrato en Markdown + cláusulas clave",
                    handoff_to=["gdpr_validation"],
                ),
                step(
                    id="gdpr_validation",
                    name="Validación GDPR",
                    agent="JUSTICIA",
                    action_type="compliance_check",
                    description="Validar tratamientos de datos y flujos compartidos con PERSEO.",
                    depends_on=["contract_blueprint"],
                    expected_output="Checklist GDPR con severidad.",
                    handoff_to=["digital_sign"],
                ),
                step(
                    id="digital_sign",
                    name="Firma digital",
                    agent="JUSTICIA",
                    action_type="document_signed",
                    description="Aplicar firma y registrar hash en panel legal.",
                    depends_on=["gdpr_validation"],
                    expected_output="PDF firmado + registro audit trail.",
                ),
            ],
        ),
        TeamFlowWorkflow(
            workflow_id="rrhh_onboarding_v1",
            title="Onboarding integral RRHH",
            category="rrhh",
            summary="AFRODITA coordina fichajes, contratos y accesos.",
            success_criteria=[
                "Empleado dado de alta",
                "Contratos firmados",
                "Accesos y fichajes operativos",
            ],
            entry_conditions=["Datos de empleado", "Rol asignado"],
            default_payload={"probation_days": 90},
            steps=[
                step(
                    id="identity_check",
                    name="Verificación DNIe",
                    agent="AFRODITA",
                    action_type="task_assigned",
                    description="Parsear DNIe y validar datos básicos.",
                    expected_output="Ficha validada + detección de inconsistencias.",
                    handoff_to=["contract_rrhh"],
                ),
                step(
                    id="contract_rrhh",
                    name="Contrato laboral",
                    agent="AFRODITA",
                    action_type="contract_creator_rrhh",
                    description="Generar contrato laboral y enviarlo a JUSTICIA si requiere revisión.",
                    depends_on=["identity_check"],
                    expected_output="Contrato listo para firma + resumen payroll.",
                    handoff_to=["access_ready"],
                ),
                step(
                    id="access_ready",
                    name="Accesos + fichaje",
                    agent="THALOS",
                    action_type="task_assigned",
                    description="Configurar credenciales iniciales y fichaje por QR/facial.",
                    depends_on=["contract_rrhh"],
                    expected_output="Checklist de accesos y dispositivos revocables.",
                ),
            ],
        ),
        TeamFlowWorkflow(
            workflow_id="ads_launch_v1",
            title="Lanzamiento express Ads",
            category="ads",
            summary="Pipeline rápido para lanzar campañas pagadas con PERSEO.",
            success_criteria=[
                "Plan de medios generado",
                "Activos aprobados",
                "Campañas con presupuesto piloto activo",
            ],
            entry_conditions=["Brief comercial", "Presupuesto aprobado"],
            default_payload={"channels": ["Meta", "Google"]},
            steps=[
                step(
                    id="assets_audit",
                    name="Análisis creativos",
                    agent="PERSEO",
                    action_type="image_analyzer",
                    description="Analizar assets y detectar gaps.",
                    expected_output="Informe de colorimetría y copy hooks.",
                    handoff_to=["ads_blueprint"],
                ),
                step(
                    id="ads_blueprint",
                    name="Blueprint de campañas",
                    agent="PERSEO",
                    action_type="ads_campaign_builder",
                    description="Plan de campañas + KPIs por canal.",
                    depends_on=["assets_audit"],
                    expected_output="Plan listo para cargar en plataformas.",
                    handoff_to=["legal_fasttrack"],
                ),
                step(
                    id="legal_fasttrack",
                    name="Validación expres",
                    agent="JUSTICIA",
                    action_type="document_reviewed",
                    description="Revisar claims y requisitos legales.",
                    depends_on=["ads_blueprint"],
                    expected_output="Go/No-Go legal para creatividades.",
                ),
            ],
        ),
    ]

    return {wf.workflow_id: wf for wf in workflows}


class TeamFlowEngine:
    """Motor central para coordinar workflows entre agentes."""

    def __init__(self) -> None:
        self._workflows = _build_workflows()
        self._last_validation: Optional[Dict[str, Any]] = None
        self._shared_context: Dict[str, Dict[str, Any]] = {}

    def list_workflows(self) -> List[Dict[str, Any]]:
        """Resumen de workflows disponibles."""
        return [
            {
                "id": wf.workflow_id,
                "title": wf.title,
                "summary": wf.summary,
                "category": wf.category,
                "agents": wf.agents,
                "sla_minutes": wf.sla_minutes,
                "steps": [
                    {
                        "id": step.id,
                        "agent": step.agent,
                        "action": step.action_type,
                        "depends_on": step.depends_on,
                    }
                    for step in wf.steps
                ],
            }
            for wf in self._workflows.values()
        ]

    def get_workflow(self, workflow_id: str) -> TeamFlowWorkflow:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' no encontrado")
        return workflow

    def connect_agents(self, workflow_id: str) -> Dict[str, List[str]]:
        """Mapa de dependencias entre agentes para un workflow."""
        workflow = self.get_workflow(workflow_id)
        graph: Dict[str, set[str]] = {}
        for step in workflow.steps:
            graph.setdefault(step.agent, set())
            for handoff in step.handoff_to:
                target_step = next((s for s in workflow.steps if s.id == handoff), None)
                if target_step:
                    graph[step.agent].add(target_step.agent)
        return {agent: sorted(targets) for agent, targets in graph.items()}

    def validate_integrations(self) -> Dict[str, Any]:
        """Valida integraciones básicas requeridas por los workflows."""
        from app.core.config import settings  # import tardío para evitar ciclos

        checks = {
            "openai": bool(settings.SECRET_KEY and settings.DEBUG is not None),
            "stripe": bool(settings.SECRET_KEY),  # placeholder sin exponer keys
            "uploads": Path(settings.STATIC_DIR).exists(),
            "agent_to_agent": True,
        }
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "ready" if all(checks.values()) else "degraded",
            "checks": checks,
        }
        self._last_validation = result
        return result

    def run_workflow(
        self,
        workflow_id: str,
        payload: Optional[Dict[str, Any]] = None,
        actor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crea tareas en activity logger para cada paso del workflow."""
        workflow = self.get_workflow(workflow_id)
        execution_id = str(uuid4())
        base_payload = {**workflow.default_payload, **(payload or {})}
        created_tasks: List[Dict[str, Any]] = []

        for step in workflow.steps:
            context = {
                "workflow_id": workflow.workflow_id,
                "execution_id": execution_id,
                "step_id": step.id,
                "depends_on": step.depends_on,
                "payload": base_payload,
                **step.metadata,
            }
            activity = ActivityLogger.log_activity(
                agent_name=step.agent,
                action_type=step.action_type,
                action_description=f"[TeamFlow:{workflow.workflow_id}] {step.description}",
                details=context,
                status="pending" if step.depends_on else "in_progress",
                priority="high",
                visible_to_client=True,
                metrics={"expected_output": step.expected_output},
                user_email=actor,
            )
            created_tasks.append(
                {
                    "step_id": step.id,
                    "agent": step.agent,
                    "activity_id": activity.id if activity else None,
                    "status": activity.status if activity else "pending",
                }
            )

        self._shared_context[execution_id] = {
            "workflow": workflow.workflow_id,
            "payload": base_payload,
            "created_by": actor,
            "tasks": created_tasks,
        }

        return {
            "workflow": workflow.workflow_id,
            "execution_id": execution_id,
            "created_tasks": created_tasks,
            "agents": workflow.agents,
            "summary": workflow.summary,
            "success_criteria": workflow.success_criteria,
        }

    def get_shared_context(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el contexto compartido de una ejecución."""
        return self._shared_context.get(execution_id)

    def update_shared_context(self, execution_id: str, data: Dict[str, Any]) -> None:
        if execution_id not in self._shared_context:
            self._shared_context[execution_id] = data
        else:
            self._shared_context[execution_id].update(data)


teamflow_engine = TeamFlowEngine()


