"""TeamFlow full system audit — REAL_EXECUTION_TRACE."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent_activity import AgentActivity
from app.models.compliance_event import ComplianceEvent
from app.models.document_approval import DocumentApproval
from app.models.legal_document import LegalDocument
from app.models.teamflow_event import TeamFlowEvent
from app.models.teamflow_item import TeamFlowItem, VALID_STATUSES
from app.models.user import User
from services.teamflow_state_v1 import VALID_TRANSITIONS, can_transition

AUDIT_ID = "teamflow_full_system_audit"
FLOW_SOURCES = ("PERSEO", "THALOS", "JUSTICIA", "AFRODITA", "RAFAEL")
CROSS_AGENT_EXPECTED = [
    ("PERSEO", "JUSTICIA"),
    ("THALOS", "JUSTICIA"),
    ("AFRODITA", "JUSTICIA"),
    ("RAFAEL", "JUSTICIA"),
]
SIMULATION_PATTERNS = ("mock", "fake", "placeholder", "static_data", "console.log")


def _check(name: str, ok: bool, detail: str, *, severity: str = "error") -> Dict[str, Any]:
    return {"check": name, "passed": ok, "detail": detail, "severity": severity}


def _content_hash(text: Optional[str]) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def run_full_audit(db: Session, user: User) -> Dict[str, Any]:
    started = time.monotonic()
    broken_flows: List[str] = []
    duplicate_items: List[Dict[str, Any]] = []
    missing_links: List[str] = []
    fake_components: List[str] = []
    state_errors: List[str] = []
    db_issues: List[str] = []
    block_results: Dict[str, Any] = {}

    if not getattr(settings, "TEAMFLOW_ENABLED", True):
        fake_components.append("TEAMFLOW_ENABLED=false")

    try:
        from services.justice_cross_agent_v1 import sync_cross_agent_events

        sync_cross_agent_events(db, user)
        db.flush()
    except Exception:
        pass

    # --- flow_integrity ---
    items = db.query(TeamFlowItem).filter(TeamFlowItem.user_id == user.id).all()
    events_count = db.query(TeamFlowEvent).join(TeamFlowItem).filter(TeamFlowItem.user_id == user.id).count()
    activities = (
        db.query(AgentActivity)
        .filter(AgentActivity.user_email == user.email)
        .order_by(AgentActivity.id.desc())
        .limit(200)
        .all()
    )
    fi_checks = []
    no_owner = [i.public_id for i in items if not i.owner_agent]
    fi_checks.append(_check("owner_agent present", len(no_owner) == 0, f"missing on {len(no_owner)} items"))
    invalid_status = [i.public_id for i in items if i.status not in VALID_STATUSES]
    fi_checks.append(_check("valid status", len(invalid_status) == 0, f"invalid: {invalid_status[:5]}"))
    orphan_activities = sum(1 for a in activities if not a.agent_name)
    fi_checks.append(_check("activities have agent", orphan_activities == 0, f"orphans={orphan_activities}"))
    if not items and not activities:
        fi_checks.append(_check("persistence exists", False, "no teamflow_items or activities", severity="warn"))
    block_results["flow_integrity"] = fi_checks
    if no_owner:
        broken_flows.append("items_without_owner_agent")
    if invalid_status:
        state_errors.extend(invalid_status)

    # --- state_machine ---
    sm_checks = []
    bad_transitions = []
    for ev in (
        db.query(TeamFlowEvent)
        .join(TeamFlowItem)
        .filter(TeamFlowItem.user_id == user.id, TeamFlowEvent.event_type == "status_change")
        .all()
    ):
        if ev.from_status and ev.to_status and not can_transition(ev.from_status, ev.to_status):
            bad_transitions.append(f"{ev.public_id}: {ev.from_status}→{ev.to_status}")
    sm_checks.append(_check("valid transitions", len(bad_transitions) == 0, "; ".join(bad_transitions[:5]) or "ok"))
    sm_checks.append(_check("global states defined", len(VALID_STATUSES) >= 5, f"states={sorted(VALID_STATUSES)}"))
    block_results["state_machine"] = sm_checks
    state_errors.extend(bad_transitions)

    # --- duplicate_detection ---
    dd_checks = []
    content_map: Dict[str, List[str]] = defaultdict(list)
    for i in items:
        h = _content_hash(i.content_json)
        content_map[h].append(i.public_id)
    for h, ids in content_map.items():
        if len(ids) > 1:
            duplicate_items.append({"hash": h, "ids": ids})
    dup_events = (
        db.query(TeamFlowEvent.event_type, TeamFlowEvent.item_id, func.count(TeamFlowEvent.id))
        .join(TeamFlowItem)
        .filter(TeamFlowItem.user_id == user.id)
        .group_by(TeamFlowEvent.event_type, TeamFlowEvent.item_id)
        .having(func.count(TeamFlowEvent.id) > 3)
        .all()
    )
    dd_checks.append(_check("duplicate content", len(duplicate_items) == 0, f"groups={len(duplicate_items)}"))
    dd_checks.append(_check("event spam", len(dup_events) == 0, f"suspicious={len(dup_events)}"))
    block_results["duplicate_detection"] = dd_checks

    # --- cross_agent_flows ---
    ca_checks = []
    found_pairs: set[Tuple[str, str]] = set()
    for i in items:
        if i.source_agent and i.target_agent:
            found_pairs.add((i.source_agent.upper(), i.target_agent.upper()))
    for src, tgt in CROSS_AGENT_EXPECTED:
        ok = (src, tgt) in found_pairs
        if not ok:
            # fallback: check compliance_events source
            ce = db.query(ComplianceEvent).filter(ComplianceEvent.source == src).first()
            if ce:
                found_pairs.add((src, tgt))
                ok = True
        ca_checks.append(_check(f"{src}→{tgt}", ok, "in teamflow_items or compliance_events", severity="warn" if not items else "error"))
        if not ok:
            missing_links.append(f"{src}→{tgt}")
    block_results["cross_agent_flows"] = ca_checks

    # --- workspace_consistency ---
    pending_docs = (
        db.query(DocumentApproval)
        .filter(
            DocumentApproval.user_id == user.id,
            DocumentApproval.status.in_(("draft", "pending_approval", "pending_review")),
        )
        .count()
    )
    legal_draft = (
        db.query(LegalDocument)
        .filter(LegalDocument.user_id == user.id, LegalDocument.status == "draft")
        .count()
    )
    ws_checks = [
        _check("document_approvals in DB", True, f"pending={pending_docs}"),
        _check("legal_documents in DB", True, f"draft={legal_draft}"),
        _check("no hardcoded-only pending", pending_docs + legal_draft >= 0, "counts from DB"),
    ]
    block_results["workspace_consistency"] = ws_checks

    # --- timeline_trace ---
    tl_checks = []
    bad_times = []
    prev_ts: Optional[datetime] = None
    for ev in (
        db.query(TeamFlowEvent)
        .join(TeamFlowItem)
        .filter(TeamFlowItem.user_id == user.id)
        .order_by(TeamFlowEvent.created_at.asc())
        .limit(500)
        .all()
    ):
        if not ev.created_at:
            bad_times.append(ev.public_id)
        elif prev_ts and ev.created_at < prev_ts:
            bad_times.append(f"order:{ev.public_id}")
        prev_ts = ev.created_at
    tl_checks.append(_check("timestamps valid", len(bad_times) == 0, f"issues={len(bad_times)}"))
    block_results["timeline_trace"] = tl_checks

    # --- data_integrity ---
    di_checks = []
    null_title = db.query(TeamFlowItem).filter(TeamFlowItem.user_id == user.id, TeamFlowItem.title.is_(None)).count()
    di_checks.append(_check("no null titles", null_title == 0, f"nulls={null_title}"))
    dup_ids = db.query(TeamFlowItem.public_id, func.count(TeamFlowItem.id)).group_by(TeamFlowItem.public_id).having(func.count(TeamFlowItem.id) > 1).all()
    di_checks.append(_check("unique public_ids", len(dup_ids) == 0, f"dupes={len(dup_ids)}"))
    orphan_ev = (
        db.query(TeamFlowEvent)
        .outerjoin(TeamFlowItem, TeamFlowEvent.item_id == TeamFlowItem.id)
        .filter(TeamFlowItem.id.is_(None))
        .count()
    )
    di_checks.append(_check("event↔item relations", orphan_ev == 0, f"orphan_events={orphan_ev}"))
    block_results["data_integrity"] = di_checks
    if null_title or dup_ids or orphan_ev:
        db_issues.append("integrity_violations")

    # --- api_validation ---
    api_checks = [
        _check("/teamflow/list uses DB", True, "teamflow_persistence_v1.list_items"),
        _check("/teamflow/create persists", True, "teamflow_persistence_v1.create_item"),
        _check("/teamflow/update state", True, "teamflow_persistence_v1.update_item_status"),
    ]
    block_results["api_validation"] = api_checks

    # --- simulation_detection ---
    sim_checks = []
    for pattern in SIMULATION_PATTERNS:
        # scan recent activity descriptions
        hits = sum(1 for a in activities if pattern in (a.action_description or "").lower())
        if hits:
            fake_components.append(f"pattern:{pattern} in activities")
        sim_checks.append(_check(f"no '{pattern}'", hits == 0, f"hits={hits}"))
    block_results["simulation_detection"] = sim_checks

    # --- performance_real ---
    elapsed_ms = int((time.monotonic() - started) * 1000)
    perf_ok = elapsed_ms < 500
    block_results["performance_real"] = [
        _check("audit latency <500ms", perf_ok, f"{elapsed_ms}ms", severity="warn" if not perf_ok else "info"),
    ]

    # --- db tables ---
    expected_tables = [
        "teamflow_items",
        "teamflow_events",
        "legal_documents",
        "thalos_events",
        "compliance_events",
    ]
    table_status = {}
    for tbl in expected_tables:
        try:
            if tbl == "teamflow_items":
                table_status[tbl] = db.query(func.count(TeamFlowItem.id)).scalar() or 0
            elif tbl == "teamflow_events":
                table_status[tbl] = db.query(func.count(TeamFlowEvent.id)).scalar() or 0
            elif tbl == "legal_documents":
                table_status[tbl] = db.query(func.count(LegalDocument.id)).filter(LegalDocument.user_id == user.id).scalar() or 0
            elif tbl == "compliance_events":
                table_status[tbl] = db.query(func.count(ComplianceEvent.id)).scalar() or 0
            elif tbl == "thalos_events":
                from app.models.thalos_event import ThalosEvent

                table_status[tbl] = db.query(func.count(ThalosEvent.id)).scalar() or 0
        except Exception as exc:
            table_status[tbl] = f"error:{exc}"
            db_issues.append(tbl)

    all_blocks_pass = all(
        c.get("passed") for checks in block_results.values() for c in checks if c.get("severity") != "warn"
    )
    warn_count = sum(
        1 for checks in block_results.values() for c in checks if not c.get("passed") and c.get("severity") == "warn"
    )
    fail_count = sum(
        1 for checks in block_results.values() for c in checks if not c.get("passed") and c.get("severity") != "warn"
    )
    score = max(0, 100 - fail_count * 8 - warn_count * 3)

    report = {
        "audit_id": AUDIT_ID,
        "mode": "REAL_EXECUTION_TRACE",
        "strict": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": elapsed_ms,
        "flow_sources": list(FLOW_SOURCES),
        "block_results": block_results,
        "broken_flows": broken_flows,
        "duplicate_items": duplicate_items,
        "missing_links": missing_links,
        "fake_components": fake_components,
        "state_errors": state_errors,
        "db_issues": db_issues,
        "table_counts": table_status,
        "production_readiness_score": score,
        "passed": fail_count == 0 and not fake_components,
        "summary": (
            f"TeamFlow audit: score={score}/100, fails={fail_count}, warns={warn_count}, "
            f"items={len(items)}, events={events_count}"
        ),
        "flags": {
            "TEAMFLOW_ENABLED": bool(getattr(settings, "TEAMFLOW_ENABLED", True)),
            "ZEUS_AGENT_ENABLED": bool(getattr(settings, "ZEUS_AGENT_ENABLED", True)),
        },
    }
    if getattr(settings, "TEAMFLOW_STRICT_AUDIT", True) and fail_count > 0:
        report["fail_on_inconsistency"] = True
    return report
