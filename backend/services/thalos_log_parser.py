"""THALOS log parser — raw lines → structured events with severity."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

SEVERITY_PATTERNS = (
    (re.compile(r"\b(critical|fatal|panic)\b", re.I), "critical"),
    (re.compile(r"\b(error|exception|traceback|failed)\b", re.I), "error"),
    (re.compile(r"\b(warn|warning)\b", re.I), "warning"),
    (re.compile(r"\b(info|login ok|started)\b", re.I), "info"),
)

THREAT_PATTERNS = (
    ("failed login", "auth_failure", "high"),
    ("unauthorized", "access_denied", "high"),
    ("brute", "brute_force", "critical"),
    ("drop table", "sql_injection", "critical"),
    ("union select", "sql_injection", "critical"),
    ("403", "forbidden", "medium"),
    ("invalid credentials", "auth_failure", "medium"),
    ("rate limit", "rate_limit", "medium"),
)


def classify_severity(line: str) -> str:
    for pattern, severity in SEVERITY_PATTERNS:
        if pattern.search(line):
            return severity
    return "info"


def detect_event_type(line: str) -> tuple[str, str]:
    lower = line.lower()
    for needle, event_type, min_sev in THREAT_PATTERNS:
        if needle in lower:
            return event_type, min_sev
    if "login" in lower:
        return "login_activity", "info"
    if "backup" in lower:
        return "backup_activity", "info"
    return "log_line", classify_severity(line)


def parse_log_line(line: str, *, source: str = "log_file") -> Optional[Dict[str, Any]]:
    text = (line or "").strip()
    if not text:
        return None
    event_type, threat_sev = detect_event_type(text)
    severity = threat_sev if threat_sev != "info" else classify_severity(text)
    return {
        "event_type": event_type,
        "severity": severity,
        "message": text[:2000],
        "source": source,
        "metadata": {"raw_length": len(text), "parser": "thalos_log_parser_v1"},
    }


def parse_log_lines(lines: List[str], *, source: str = "log_stream") -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in lines:
        parsed = parse_log_line(line, source=source)
        if parsed:
            events.append(parsed)
    return events


def serialize_metadata(meta: Dict[str, Any]) -> str:
    return json.dumps(meta, ensure_ascii=False, default=str)
