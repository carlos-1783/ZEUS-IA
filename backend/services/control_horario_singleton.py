"""Instancia de ControlHorarioService usada SOLO para catalogo de perfiles/config.

Fase 2 / hosteleria: ya no guarda estado por empleado (active_records/employees/schedules).
Los fichajes viven solo en BD (time_cost_engine_v1); este objeto se comparte entre empresas
y no debe contener datos de ninguna."""
from services.control_horario_service import ControlHorarioService

control_horario_service = ControlHorarioService()
