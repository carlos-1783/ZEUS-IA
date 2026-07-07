"""Tests for zeus_core_workspace_bootstrap_v1."""

from unittest.mock import MagicMock, patch

from services.zeus_core_workspace_bootstrap_v1 import (
    ARTIFACT_TYPE,
    build_zeus_brain,
    classify_agent_capabilities,
    discover_available_agents,
    generate_intents,
    map_intents_to_agents,
    run_zeus_core_workspace_bootstrap,
)


def test_discover_available_agents_from_routes():
    with patch(
        "services.zeus_core_workspace_bootstrap_v1._all_route_paths",
        return_value=["/afrodita/rrhh/v1/status", "/perseo/status"],
    ):
        agents = discover_available_agents()
    by_name = {row["name"]: row for row in agents}
    assert by_name["AFRODITA"]["available"] is True
    assert by_name["PERSEO"]["available"] is True
    assert by_name["THALOS"]["available"] is False


def test_intent_routing_uses_capability_map():
    agents = [
        {"name": "AFRODITA", "requested_targets": [], "discovered_targets": ["/api/v1/afrodita"], "available": True},
        {"name": "RAFAEL", "requested_targets": [], "discovered_targets": [], "available": False},
        {"name": "THALOS", "requested_targets": [], "discovered_targets": ["/api/v1/thalos/v1"], "available": True},
        {"name": "JUSTICIA", "requested_targets": [], "discovered_targets": ["/api/v1/justicia/v1"], "available": True},
        {"name": "PERSEO", "requested_targets": [], "discovered_targets": ["/api/v1/perseo"], "available": True},
    ]
    capabilities = classify_agent_capabilities(agents)
    routes = map_intents_to_agents(generate_intents(), capabilities)
    risk = next(item for item in routes if item["intent"] == "analizar riesgo")
    assert risk["agent"] == "RAFAEL"
    assert risk["available"] is False


def test_build_zeus_brain_contains_workspace_target():
    brain = build_zeus_brain(
        agents=[{"name": "AFRODITA", "available": True}],
        capabilities_map={"AFRODITA": {"available": True}},
        intent_routing=[{"intent": "crear cliente"}],
        execution_map=[{"intent": "crear cliente", "agent": "AFRODITA", "action": "create_client"}],
        company_id=10,
    )
    assert brain["workspace"]["target"] == ARTIFACT_TYPE
    assert brain["workspace"]["company_id"] == 10


def test_run_bootstrap_persists_when_requested():
    db = MagicMock()
    user = MagicMock()
    user.id = 5
    with patch("services.zeus_core_workspace_bootstrap_v1.ensure_user_company_link_for_operations", return_value=9), patch(
        "services.zeus_core_workspace_bootstrap_v1.primary_company_id_for_user",
        return_value=9,
    ), patch(
        "services.zeus_core_workspace_bootstrap_v1.persist_workspace_config",
        return_value={"document_id": 11},
    ):
        out = run_zeus_core_workspace_bootstrap(db, user=user, analysis_only=True, persist_artifact=True)
    assert out["success"] is True
    assert out["stored_workspace_config"] == {"document_id": 11}
