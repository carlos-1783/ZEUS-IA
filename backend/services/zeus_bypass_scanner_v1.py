"""
Escáner estático zeus_phase_2 — detecta bypass de mutaciones fuera del guard.

Uso: python -m services.zeus_bypass_scanner_v1
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

BACKEND_ROOT = Path(__file__).resolve().parent.parent

SCAN_SCOPES = ("api", "services", "agents", "scripts", "app")

PATTERNS: List[tuple[str, re.Pattern[str]]] = [
    ("is_active_assign", re.compile(r"\.is_active\s*=", re.I)),
    ("db_commit", re.compile(r"\bdb\.commit\s*\(", re.I)),
    ("db_execute", re.compile(r"\bdb\.execute\s*\(", re.I)),
    ("engine_execute", re.compile(r"\bengine\.execute\s*\(", re.I)),
    ("update_users", re.compile(r"update\s*\(\s*users|UPDATE\s+users", re.I)),
    ("delete_users", re.compile(r"delete\s*\(\s*users|DELETE\s+FROM\s+users|db\.delete\s*\(\s*user", re.I)),
    ("session_query", re.compile(r"\b(session|db)\.query\s*\(", re.I)),
    ("raw_sql", re.compile(r"cursor\.execute\s*\(|text\s*\(\s*[\"']", re.I)),
    ("cashflow_direct", re.compile(r"CashflowLedgerEntry\s*\(", re.I)),
    ("user_delete", re.compile(r"db\.delete\s*\(\s*user\b", re.I)),
]

ALLOWED_PATH_FRAGMENTS = frozenset(
    {
        "zeus_core_guard_v1.py",
        "user_service_v1.py",
        "zeus_bypass_scanner_v1.py",
        "zeus_runtime_guard_v1.py",
        "test_",
        "tests/",
        "alembic/versions/",
        "conftest.py",
    }
)

READ_ONLY_CONTEXT = frozenset(
    {
        "is_active ==",
        "is_active==",
        "filter(",
        "Filter(",
    }
)


@dataclass
class Violation:
    file: str
    line: int
    pattern: str
    snippet: str
    category: str
    scope: str
    recommendation: str = ""


@dataclass
class ScanReport:
    task: str = "zeus_phase_2_full_system_audit_and_patch"
    violations: List[Violation] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    coverage: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "violations": [asdict(v) for v in self.violations],
            "summary": self.summary,
            "coverage": self.coverage,
        }


def _scope_for(path: Path) -> str:
    parts = path.parts
    for s in SCAN_SCOPES:
        if s in parts:
            return s
    return "other"


def _is_allowed(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(frag in s for frag in ALLOWED_PATH_FRAGMENTS)


def _classify(path: Path, pattern: str, line_text: str, scope: str) -> tuple[str, str]:
    lt = line_text.strip()
    if any(ctx in lt for ctx in READ_ONLY_CONTEXT) and "is_active_assign" in pattern:
        return "false_positive", "Lectura/filtro, no mutación"

    if "test" in str(path).lower():
        return "false_positive", "Archivo de test"

    financial = pattern in ("cashflow_direct",) or "Invoice(" in lt
    user_mut = pattern in ("is_active_assign", "delete_users", "user_delete", "update_users")

    if user_mut and "is_active = True" in lt or "is_active=True" in lt:
        return "legacy_safe", "Activación de cuenta — revisar si requiere guard en reactivación"

    if user_mut and ("is_active = False" in lt or "is_active=False" in lt):
        return "critical_bypass", "Usar user_service_v1.secure_deactivate()"

    if financial and scope == "api":
        return "critical_bypass", "Mover a service layer con financial_integrity_v1"

    if financial and scope == "services" and "cashflow_ledger_service" not in str(path):
        return "requires_wrapper", "Delegar en cashflow_ledger_service.record_movement()"

    if scope == "scripts":
        return "requires_wrapper", "Envolver con zeus_script_guard_v1.guarded_execution()"

    if scope == "api" and pattern in ("db_commit", "session_query"):
        return "requires_wrapper", "Endpoint debe delegar en service; auditar guard"

    if pattern in ("db_execute", "engine_execute", "raw_sql"):
        if "SELECT 1" in lt.upper() or "health" in str(path).lower():
            return "false_positive", "Health check / lectura"
        return "requires_wrapper", "SQL raw — auditar y envolver"

    if scope in ("agents", "services") and pattern == "db_commit":
        return "legacy_safe", "Commit en service — verificar pasa por guard"

    return "legacy_safe", "Revisar manualmente"


def scan_file(path: Path) -> List[Violation]:
    if _is_allowed(path):
        return []
    if path.suffix != ".py":
        return []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    scope = _scope_for(path)
    hits: List[Violation] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for pname, pat in PATTERNS:
            if not pat.search(line):
                continue
            cat, rec = _classify(path, pname, line, scope)
            hits.append(
                Violation(
                    file=str(path.relative_to(BACKEND_ROOT)),
                    line=i,
                    pattern=pname,
                    snippet=line.strip()[:200],
                    category=cat,
                    scope=scope,
                    recommendation=rec,
                )
            )
    return hits


def scan_codebase(root: Optional[Path] = None) -> ScanReport:
    root = root or BACKEND_ROOT
    report = ScanReport()
    py_files = list(root.rglob("*.py"))
    total_files = len(py_files)

    for fp in py_files:
        if any(
            p in fp.parts
            for p in ("node_modules", ".venv", "venv", "__pycache__", "site-packages")
        ):
            continue
        report.violations.extend(scan_file(fp))

    cats: Dict[str, int] = {}
    for v in report.violations:
        cats[v.category] = cats.get(v.category, 0) + 1

    critical_files: Set[str] = {v.file for v in report.violations if v.category == "critical_bypass"}
    wrapped_modules = {
        "zeus_core_guard_v1",
        "user_service_v1",
        "financial_integrity_v1",
        "legacy_handler_guard_v1",
        "thalos_executor",
        "zeus_runtime_guard_v1",
    }

    report.summary = {
        "total_files_scanned": total_files,
        "total_hits": len(report.violations),
        **cats,
    }
    report.coverage = {
        "critical_bypass_files": sorted(critical_files),
        "critical_bypass_count": cats.get("critical_bypass", 0),
        "requires_wrapper_count": cats.get("requires_wrapper", 0),
        "false_positive_count": cats.get("false_positive", 0),
        "legacy_safe_count": cats.get("legacy_safe", 0),
        "guarded_modules": sorted(wrapped_modules),
        "estimated_guarded_mutation_pct": round(
            100.0
            * (1.0 - cats.get("critical_bypass", 0) / max(len(report.violations), 1)),
            1,
        ),
    }
    return report


def scan_endpoints(root: Optional[Path] = None) -> Dict[str, Any]:
    """Detecta endpoints con db.commit/db.query directo."""
    root = root or (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints")
    unguarded: List[Dict[str, Any]] = []
    total = 0

    for fp in root.rglob("*.py"):
        text = fp.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not any(
                isinstance(d, ast.Attribute) and d.attr in ("get", "post", "put", "delete", "patch")
                for d in ast.walk(node)
            ):
                continue
            total += 1
            body_src = ast.get_source_segment(text, node) or ""
            has_db = "db.query" in body_src or "db.commit" in body_src
            has_service = "services." in body_src or "_svc" in body_src or "Service" in body_src
            if has_db and not has_service:
                unguarded.append(
                    {
                        "file": str(fp.relative_to(BACKEND_ROOT)),
                        "function": node.name,
                        "line": node.lineno,
                        "has_direct_db": has_db,
                    }
                )

    return {
        "endpoints_scanned": total,
        "unguarded_endpoints": unguarded,
        "unguarded_count": len(unguarded),
    }


def run_full_audit() -> Dict[str, Any]:
    code_report = scan_codebase()
    endpoint_report = scan_endpoints()
    return {
        "code_scan": code_report.to_dict(),
        "endpoint_scan": endpoint_report,
        "runtime_guard": "zeus_runtime_guard_v1 (attach on startup when closure enabled)",
    }


if __name__ == "__main__":
    result = run_full_audit()
    print(json.dumps(result, indent=2, ensure_ascii=False))
