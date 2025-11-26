"""
Herramientas de workspace para AFRODITA.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List

from .base import log_tool_execution


def _hash_employee(employee_id: str) -> int:
    return int(hashlib.sha256(employee_id.encode("utf-8")).hexdigest(), 16)


def record_face_check_in(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Simular coincidencia facial usando embeddings."""
    employee_id = payload.get("employee_id", "UNKNOWN")
    embedding = payload.get("embedding", [])
    reference_seed = _hash_employee(employee_id) % 100
    match_score = min(99, reference_seed if embedding else 42)

    result = {
        "employee_id": employee_id,
        "match_score": match_score,
        "status": "approved" if match_score > 60 else "manual_review",
        "timestamp": payload.get("timestamp") or datetime.utcnow().isoformat(),
    }
    log_tool_execution("AFRODITA", "face_check_in", "Check-in por rostro", {"payload": payload, "result": result})
    return result


def handle_qr_check_in(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Procesar QR con formato ZEUSCHECK|EMPID|timestamp."""
    code = payload.get("qr_code", "")
    parts = code.split("|")
    result = {
        "raw": code,
        "employee_id": parts[1] if len(parts) > 1 else None,
        "timestamp": parts[2] if len(parts) > 2 else datetime.utcnow().isoformat(),
        "status": "valid" if parts[:1] == ["ZEUSCHECK"] else "invalid",
    }
    log_tool_execution("AFRODITA", "qr_check_in", "QR de fichaje procesado", {"result": result})
    return result


def build_employee_schedule(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generar cuadrante básico de turnos."""
    employees: List[Dict[str, Any]] = payload.get("employees", [])
    shifts = ["mañana", "tarde", "noche"]
    schedule = [
        {
            "employee": emp.get("name"),
            "shift": shifts[idx % len(shifts)],
            "coverage": "tienda" if idx % 2 == 0 else "soporte",
        }
        for idx, emp in enumerate(employees)
    ]
    result = {"schedule": schedule, "week": payload.get("week", "current")}
    log_tool_execution("AFRODITA", "employee_manager", "Turnos generados", {"result": result})
    return result


def create_rrhh_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generar contrato laboral simplificado."""
    name = payload.get("employee_name")
    role = payload.get("role")
    salary = payload.get("salary", 0)
    contract_type = payload.get("contract_type", "indefinido")

    clauses = [
        f"Empleado: {name}",
        f"Cargo: {role}",
        f"Salario anual bruto: €{salary:,.2f}",
        f"Tipo de contrato: {contract_type}",
        "Periodo de prueba: 3 meses",
        "Plan de rotación para onboarding + pairing semanal",
    ]
    result = {"clauses": clauses, "status": "draft"}
    log_tool_execution("AFRODITA", "contract_creator_rrhh", "Contrato RRHH generado", {"result": result})
    return result

