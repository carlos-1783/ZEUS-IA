"""
ZEUS CORE: informe de coordinacion con datos reales de la empresa.

Fase 2 / Step 2 (sin simulacion): antes devolvia un texto fijo ("Plan maestro activo",
"No se detectan bloqueos criticos", "Legal listo con JUSTICIA"...) a cualquier empresa,
incluida cada empresa nueva al darse de alta. Ahora el informe sale de la BD, filtrado por
la empresa de la actividad: actividad por agente y estado, fallos y aprobaciones pendientes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.zeus_pending_approval import ZeusPendingApproval
from .. import utils

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
_PROBLEM_STATUSES = ("failed", "blocked", "blocked_missing_handler", "blocked_no_company", "blocked_client_origin")


def build_coordination_report(db, company_id: int, *, exclude_activity_id: Optional[int] = None) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    q = db.query(AgentActivity.agent_name, AgentActivity.status, func.count(AgentActivity.id)).filter(
        AgentActivity.company_id == company_id, AgentActivity.created_at >= since
    )
    if exclude_activity_id is not None:
        q = q.filter(AgentActivity.id != exclude_activity_id)
    by_agent: Dict[str, Dict[str, int]] = defaultdict(dict)
    total = 0
    for agent, status, n in q.group_by(AgentActivity.agent_name, AgentActivity.status).all():
        by_agent[(agent or "?").upper()][status or "?"] = int(n)
        total += int(n)

    problems = (
        db.query(AgentActivity)
        .filter(
            AgentActivity.company_id == company_id,
            AgentActivity.created_at >= since,
            AgentActivity.status.in_(_PROBLEM_STATUSES),
        )
        .order_by(AgentActivity.id.desc())
        .limit(10)
        .all()
    )
    pending = (
        db.query(ZeusPendingApproval.agent_name, func.count(ZeusPendingApproval.id))
        .filter(ZeusPendingApproval.company_id == company_id, ZeusPendingApproval.status == "pending")
        .group_by(ZeusPendingApproval.agent_name)
        .all()
    )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "company_id": company_id,
        "window_days": WINDOW_DAYS,
        "activities_total": total,
        "activities_by_agent": {k: dict(v) for k, v in sorted(by_agent.items())},
        "problems": [
            {
                "id": a.id,
                "agent": a.agent_name,
                "action_type": a.action_type,
                "status": a.status,
                "description": (a.action_description or "")[:200],
            }
            for a in problems
        ],
        "pending_approvals": {agent: int(n) for agent, n in pending},
        "source": "database",
    }


def _markdown(report: Dict[str, Any]) -> str:
    agents = [
        f"{agent}: " + ", ".join(f"{st}={n}" for st, n in sorted(stats.items()))
        for agent, stats in report["activities_by_agent"].items()
    ] or ["Sin actividad registrada en el periodo."]
    problems = [f"#{p['id']} {p['agent']} {p['action_type']} ({p['status']})" for p in report["problems"]] or [
        "Ninguna actividad fallida o bloqueada en el periodo."
    ]
    approvals = [f"{a}: {n}" for a, n in report["pending_approvals"].items()] or ["Ninguna."]
    return utils.summarize_markdown(
        "Informe ZEUS CORE (datos reales)",
        {
            "Periodo": f"Ultimos {report['window_days']} dias, empresa {report['company_id']}",
            "Actividad por agente": agents,
            "Fallos y bloqueos": problems,
            "Aprobaciones pendientes": approvals,
        },
    )


def _failed(msg: str) -> Dict[str, Any]:
    return {"status": "failed", "details_update": {"real_execution": False, "error": msg}, "notes": msg}


def handle_zeus_task(activity: AgentActivity) -> Dict[str, Any]:
    from services.unified_agent_runtime import _resolve_activity_company

    company_id = _resolve_activity_company(activity)
    if company_id is None:
        return _failed("Informe de coordinacion no generado: la actividad no tiene empresa resoluble.")

    db = SessionLocal()
    try:
        report = build_coordination_report(db, company_id, exclude_activity_id=activity.id)
    except Exception:
        logger.exception("[ZEUS] informe de coordinacion: fallo consultando la BD")
        return _failed("Informe de coordinacion no generado: error consultando la base de datos.")
    finally:
        db.close()

    agent = (activity.agent_name or "ZEUS").upper()
    prefix = f"{activity.id}_{activity.action_type}"
    json_path = utils.write_json(agent, prefix, report, company_id=company_id)
    markdown_path = utils.write_markdown(agent, prefix, _markdown(report), company_id=company_id)
    stored = bool(json_path)
    summary = (
        f"{report['activities_total']} actividades en {WINDOW_DAYS} dias, "
        f"{len(report['problems'])} fallidas/bloqueadas, "
        f"{sum(report['pending_approvals'].values())} aprobaciones pendientes."
    )
    return {
        "status": "completed",
        "details_update": {
            "real_execution": True,
            "automation": {
                "report": report,
                "deliverables": {"json": json_path, "markdown": markdown_path},
                "deliverables_stored": stored,
                "summary": summary,
            },
        },
        "metrics_update": {"coordination_reports": 1},
        "notes": "Informe de coordinacion (datos reales): "
        + summary
        + ("" if stored else " Entregable no guardado: almacenamiento R2 no configurado."),
    }
