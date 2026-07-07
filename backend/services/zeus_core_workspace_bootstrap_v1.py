"""ZEUS CORE workspace bootstrap — analysis-only discovery and persisted config artifact."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from services.global_company_bootstrap import ensure_user_company_link_for_operations
from services.workspace_deliverables import persist_workspace_deliverable, primary_company_id_for_user

ARTIFACT_TYPE = "ZEUS_CORE_WORKSPACE_CONFIG"
SCHEMA_VERSION = "zeus_core_workspace_bootstrap_v1"

TARGET_PREFIXES: Dict[str, List[str]] = {
    "AFRODITA": ["/api/v1/afrodita", "/api/v1/afrodita/rrhh/v1", "/api/v1/afrodita/ops/v1"],
    "RAFAEL": ["/api/v1/rafael", "/api/v1/rafael-fiscal", "/api/v1/scan"],
    "THALOS": ["/api/v1/thalos", "/api/v1/thalos/v1"],
    "JUSTICIA": ["/api/v1/justicia", "/api/v1/justicia/v1", "/api/v1/justice"],
    "PERSEO": ["/api/v1/perseo", "/api/v1/perseo/v2"],
}

CAPABILITY_RULES: Dict[str, List[str]] = {
    "AFRODITA": ["create_client", "rrhh", "ops"],
    "RAFAEL": ["risk_analysis", "scoring"],
    "THALOS": ["monitoring", "alerts"],
    "JUSTICIA": ["audit", "compliance"],
    "PERSEO": ["llm_chat", "assistant"],
}

CAPABILITY_DETAILS: Dict[str, Dict[str, List[str]]] = {
    "AFRODITA": {
        "real": ["create_employee", "qr_checkin", "list_schedules", "inventory_ops", "workspace_reads"],
        "partial": ["create_client_via_cross_agent", "ops_routes"],
    },
    "RAFAEL": {
        "real": ["generate_invoice_pdf", "generate_model_303", "payment_risk_scoring", "scan_flow"],
        "partial": ["tax_summary", "workspace_forms"],
    },
    "THALOS": {
        "real": ["monitoring", "alerts", "event_audit", "workspace_items"],
        "partial": ["active_execution_guarded"],
    },
    "JUSTICIA": {
        "real": ["system_audit", "documents_read", "compliance_review"],
        "partial": ["read_only_mixed_tools"],
    },
    "PERSEO": {
        "real": ["llm_chat", "video_edit_jobs", "audit_report"],
        "partial": ["assistant_fallbacks", "ai_generation_depends_on_provider"],
    },
}

INTENT_DEFINITIONS: List[Dict[str, Any]] = [
    {"intent": "crear cliente", "keywords": ["crear cliente", "alta cliente"], "preferred_agent": "AFRODITA"},
    {"intent": "analizar riesgo", "keywords": ["riesgo", "score", "analizar riesgo"], "preferred_agent": "RAFAEL"},
    {"intent": "ver actividad", "keywords": ["actividad", "monitor", "eventos"], "preferred_agent": "THALOS"},
    {"intent": "enviar mensaje", "keywords": ["mensaje", "chat", "assistant"], "preferred_agent": "PERSEO"},
    {"intent": "resumen negocio", "keywords": ["resumen", "negocio", "audit"], "preferred_agent": "JUSTICIA"},
]

EXECUTION_RULES: List[Dict[str, str]] = [
    {"intent": "crear cliente", "agent": "AFRODITA", "action": "create_client"},
    {"intent": "analizar riesgo", "agent": "RAFAEL", "action": "score_client"},
    {"intent": "ver actividad", "agent": "THALOS", "action": "get_activity"},
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _all_route_paths() -> List[str]:
    from app.api.v1 import api_router

    return [getattr(route, "path", "") for route in api_router.routes]


def discover_available_agents() -> List[Dict[str, Any]]:
    paths = _all_route_paths()
    agents: List[Dict[str, Any]] = []
    for agent, targets in TARGET_PREFIXES.items():
        found = [target for target in targets if any(path.startswith(target) for path in paths)]
        agents.append(
            {
                "name": agent,
                "requested_targets": targets,
                "discovered_targets": found,
                "available": bool(found),
            }
        )
    return agents


def classify_agent_capabilities(agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for row in agents:
        agent = row["name"]
        detail = CAPABILITY_DETAILS.get(agent, {})
        out[agent] = {
            "rules": CAPABILITY_RULES.get(agent, []),
            "requested_targets": row["requested_targets"],
            "discovered_targets": row["discovered_targets"],
            "available": row["available"],
            "capabilities_real": detail.get("real", []),
            "capabilities_partial": detail.get("partial", []),
            "mode": "analysis_only",
        }
    return out


def generate_intents() -> List[Dict[str, Any]]:
    return [dict(item) for item in INTENT_DEFINITIONS]


def map_intents_to_agents(intents: List[Dict[str, Any]], capabilities_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    routes: List[Dict[str, Any]] = []
    for item in intents:
        agent = item["preferred_agent"]
        cap = capabilities_map.get(agent) or {}
        routes.append(
            {
                "intent": item["intent"],
                "agent": agent,
                "available": bool(cap.get("available")),
                "matched_capabilities": cap.get("rules", []),
                "discovered_targets": cap.get("discovered_targets", []),
            }
        )
    return routes


def build_zeus_brain(
    *,
    agents: List[Dict[str, Any]],
    capabilities_map: Dict[str, Any],
    intent_routing: List[Dict[str, Any]],
    execution_map: List[Dict[str, str]],
    company_id: int,
) -> Dict[str, Any]:
    available_count = sum(1 for row in agents if row.get("available"))
    return {
        "summary": {
            "goal": "Construir el modelo mental y operativo de ZEUS CORE antes de activar ejecución",
            "mode": "analysis_only",
            "available_agents": available_count,
            "total_agents": len(agents),
            "recommended_entrypoint": "/api/v1/zeus-core/workspace-bootstrap",
        },
        "agents": capabilities_map,
        "intents": [row["intent"] for row in intent_routing],
        "intent_routing": intent_routing,
        "execution_map": execution_map,
        "workspace": {
            "target": ARTIFACT_TYPE,
            "company_id": company_id,
            "persistence_kind": "workspace_config",
            "analysis_only": True,
        },
    }


def persist_workspace_config(
    db: Session,
    *,
    user: User,
    company_id: int,
    zeus_brain: Dict[str, Any],
) -> Dict[str, Any]:
    doc = persist_workspace_deliverable(
        db,
        user_id=user.id,
        company_id=company_id,
        agent_name="ZEUS CORE",
        workspace_category="workspace_config",
        title="ZEUS CORE Workspace Bootstrap",
        content_type="workspace_config",
        content={
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "zeus_brain": zeus_brain,
        },
        status="draft",
        visible_in_workspace=True,
    )
    return {"document_id": doc.id, "title": "ZEUS CORE Workspace Bootstrap"}


def run_zeus_core_workspace_bootstrap(
    db: Session,
    *,
    user: User,
    analysis_only: bool = True,
    persist_artifact: bool = True,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    if not analysis_only:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este bootstrap solo soporta mode=analysis_only por ahora.",
        )

    ensure_user_company_link_for_operations(db, user)
    cid = company_id or primary_company_id_for_user(db, user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido para guardar configuración de workspace.")

    agents = discover_available_agents()
    capabilities_map = classify_agent_capabilities(agents)
    intents = generate_intents()
    intent_routing = map_intents_to_agents(intents, capabilities_map)
    execution_map = [dict(item) for item in EXECUTION_RULES]
    zeus_brain = build_zeus_brain(
        agents=agents,
        capabilities_map=capabilities_map,
        intent_routing=intent_routing,
        execution_map=execution_map,
        company_id=cid,
    )

    persisted: Optional[Dict[str, Any]] = None
    if persist_artifact:
        persisted = persist_workspace_config(db, user=user, company_id=cid, zeus_brain=zeus_brain)

    return {
        "success": True,
        "name": "ZEUS_CORE_WORKSPACE_BOOTSTRAP",
        "mode": "analysis_only",
        "generated_at": _utcnow(),
        "agents": agents,
        "capabilities_map": capabilities_map,
        "intents": intents,
        "intent_routing": intent_routing,
        "execution_map": execution_map,
        "zeus_brain": zeus_brain,
        "stored_workspace_config": persisted,
    }
