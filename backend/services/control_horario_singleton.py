"""Instancia única de ControlHorarioService (active_records en memoria debe ser global)."""
from services.control_horario_service import ControlHorarioService

control_horario_service = ControlHorarioService()
