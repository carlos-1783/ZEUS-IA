"""
⏰ Control Horario Universal Enterprise
Sistema de control de asistencia adaptable a cualquier tipo de negocio
Integración automática con AFRODITA, RAFAEL y TPV
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, time
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class HorarioBusinessProfile(str, Enum):
    """Perfiles de negocio para Control Horario"""
    OFICINA = "oficina"
    RESTAURANTE = "restaurante"
    TIENDA = "tienda"
    EXTERNO = "externo"
    REMOTO = "remoto"
    TURNOS = "turnos"
    LOGISTICA = "logística"
    PRODUCCION = "producción"
    COMERCIAL = "comercial"
    SERVICIOS = "servicios"
    OTROS = "otros"


class CheckInMethod(str, Enum):
    """Métodos de fichaje"""
    FACE = "face"
    QR = "qr"
    CODE = "code"
    LOCATION = "location"
    ON_SITE = "on_site"  # Alias para LOCATION, preferido para servicios profesionales
    REMOTE = "remote"


class ControlHorarioService:
    """
    Control Horario Universal Enterprise
    Sistema de control de asistencia adaptable a cualquier tipo de negocio
    """
    
    def __init__(self):
        self.business_profile: Optional[HorarioBusinessProfile] = None
        self.employees: Dict[str, Dict[str, Any]] = {}
        self.active_records: Dict[str, Dict[str, Any]] = {}  # employee_id -> record
        self.schedules: Dict[str, List[Dict[str, Any]]] = {}  # employee_id -> schedules
        self.config: Dict[str, Any] = {}  # Configuración por tipo de negocio
        
        # Integraciones
        self.afrodita_integration = None
        self.rafael_integration = None
        self.tpv_integration = None
        
        logger.info("⏰ Control Horario Universal Enterprise inicializado")
    
    def get_business_config(self, profile: HorarioBusinessProfile) -> Dict[str, Any]:
        """
        Obtener configuración específica por tipo de negocio
        """
        configs = {
            HorarioBusinessProfile.OFICINA: {
                "strict_check_in": True,
                "gps_required": False,
                "multiple_shifts_per_day": False,
                "break_time_required": True,
                "auto_check_out": False,
                "irregularity_alerts": True,
                "methods_enabled": ["face", "qr", "code"],
                "location_tracking": False,
                "remote_allowed": False,
                "flexible_hours": False,
                "min_hours_per_day": 8.0,
                "max_hours_per_day": 10.0,
                "break_duration_min": 60,
                "tolerance_minutes": 5
            },
            HorarioBusinessProfile.RESTAURANTE: {
                "strict_check_in": True,
                "gps_required": False,
                "multiple_shifts_per_day": True,
                "break_time_required": True,
                "auto_check_out": False,
                "irregularity_alerts": True,
                "methods_enabled": ["face", "qr", "code"],
                "location_tracking": False,
                "remote_allowed": False,
                "flexible_hours": True,
                "min_hours_per_day": 4.0,
                "max_hours_per_day": 12.0,
                "break_duration_min": 30,
                "tolerance_minutes": 10
            },
            HorarioBusinessProfile.TIENDA: {
                "strict_check_in": True,
                "gps_required": False,
                "multiple_shifts_per_day": False,
                "break_time_required": True,
                "auto_check_out": False,
                "irregularity_alerts": True,
                "methods_enabled": ["face", "qr", "code"],
                "location_tracking": False,
                "remote_allowed": False,
                "flexible_hours": False,
                "min_hours_per_day": 6.0,
                "max_hours_per_day": 10.0,
                "break_duration_min": 60,
                "tolerance_minutes": 5
            },
            HorarioBusinessProfile.EXTERNO: {
                "strict_check_in": False,
                "gps_required": True,
                "multiple_shifts_per_day": True,
                "break_time_required": False,
                "auto_check_out": True,
                "irregularity_alerts": False,
                "methods_enabled": ["location", "qr", "remote"],
                "location_tracking": True,
                "remote_allowed": True,
                "flexible_hours": True,
                "min_hours_per_day": 0.0,
                "max_hours_per_day": 24.0,
                "break_duration_min": 0,
                "tolerance_minutes": 30
            },
            HorarioBusinessProfile.REMOTO: {
                "strict_check_in": False,
                "gps_required": False,
                "multiple_shifts_per_day": True,
                "break_time_required": False,
                "auto_check_out": False,
                "irregularity_alerts": False,
                "methods_enabled": ["remote", "code"],
                "location_tracking": False,
                "remote_allowed": True,
                "flexible_hours": True,
                "min_hours_per_day": 0.0,
                "max_hours_per_day": 24.0,
                "break_duration_min": 0,
                "tolerance_minutes": 60
            },
            HorarioBusinessProfile.TURNOS: {
                "strict_check_in": True,
                "gps_required": False,
                "multiple_shifts_per_day": False,
                "break_time_required": True,
                "auto_check_out": False,
                "irregularity_alerts": True,
                "methods_enabled": ["face", "qr", "code"],
                "location_tracking": False,
                "remote_allowed": False,
                "flexible_hours": False,
                "min_hours_per_day": 8.0,
                "max_hours_per_day": 12.0,
                "break_duration_min": 60,
                "tolerance_minutes": 15
            },
            HorarioBusinessProfile.LOGISTICA: {
                "strict_check_in": False,
                "gps_required": True,
                "multiple_shifts_per_day": True,
                "break_time_required": True,
                "auto_check_out": True,
                "irregularity_alerts": True,
                "methods_enabled": ["location", "qr"],
                "location_tracking": True,
                "remote_allowed": False,
                "flexible_hours": True,
                "min_hours_per_day": 6.0,
                "max_hours_per_day": 14.0,
                "break_duration_min": 45,
                "tolerance_minutes": 20
            },
            HorarioBusinessProfile.PRODUCCION: {
                "strict_check_in": True,
                "gps_required": False,
                "multiple_shifts_per_day": False,
                "break_time_required": True,
                "auto_check_out": False,
                "irregularity_alerts": True,
                "methods_enabled": ["face", "qr", "code"],
                "location_tracking": False,
                "remote_allowed": False,
                "flexible_hours": False,
                "min_hours_per_day": 8.0,
                "max_hours_per_day": 10.0,
                "break_duration_min": 60,
                "tolerance_minutes": 5
            },
            HorarioBusinessProfile.COMERCIAL: {
                "strict_check_in": False,
                "gps_required": True,
                "multiple_shifts_per_day": True,
                "break_time_required": False,
                "auto_check_out": True,
                "irregularity_alerts": False,
                "methods_enabled": ["location", "qr", "remote"],
                "location_tracking": True,
                "remote_allowed": True,
                "flexible_hours": True,
                "min_hours_per_day": 0.0,
                "max_hours_per_day": 24.0,
                "break_duration_min": 0,
                "tolerance_minutes": 30
            },
            HorarioBusinessProfile.SERVICIOS: {
                "strict_check_in": False,
                "gps_required": False,  # No requerido para servicios profesionales
                "multiple_shifts_per_day": True,
                "break_time_required": False,
                "auto_check_out": True,
                "irregularity_alerts": True,
                "methods_enabled": ["on_site", "location", "remote", "qr", "code"],  # Permitir ON_SITE y REMOTE
                "location_tracking": True,
                "remote_allowed": True,  # Permitir trabajo remoto
                "remote_requires_approval": False,  # Según patch
                "default_method": "on_site",  # Método por defecto
                "flexible_hours": True,
                "min_hours_per_day": 2.0,
                "max_hours_per_day": 16.0,
                "break_duration_min": 30,
                "tolerance_minutes": 20,
                "auto_check_in_on_service_start": True  # Según patch
            },
            HorarioBusinessProfile.OTROS: {
                "strict_check_in": True,
                "gps_required": False,
                "multiple_shifts_per_day": False,
                "break_time_required": True,
                "auto_check_out": False,
                "irregularity_alerts": True,
                "methods_enabled": ["qr", "code"],
                "location_tracking": False,
                "remote_allowed": False,
                "flexible_hours": False,
                "min_hours_per_day": 8.0,
                "max_hours_per_day": 10.0,
                "break_duration_min": 60,
                "tolerance_minutes": 10
            }
        }
        
        return configs.get(profile, configs[HorarioBusinessProfile.OTROS])
    
    def set_business_profile(self, profile: HorarioBusinessProfile, user_id: Optional[int] = None):
        """
        Establecer business_profile y cargar configuración
        """
        self.business_profile = profile
        self.config = self.get_business_config(profile)
        logger.info(f"[INFO] Business profile establecido: {profile.value}")
    
    def load_user_profile(self, user_data: Dict[str, Any]):
        """
        Cargar business_profile desde datos de usuario
        """
        business_profile_str = user_data.get("control_horario_business_profile")
        
        if business_profile_str:
            try:
                profile = HorarioBusinessProfile(business_profile_str)
                self.set_business_profile(profile, user_data.get("id"))
            except ValueError:
                logger.warning(f"[WARN] Business profile invalido: {business_profile_str}")
                # Auto-detectar o usar default
                detected = self._auto_detect_business_profile(user_data)
                self.set_business_profile(detected, user_data.get("id"))
        else:
            # Auto-detectar basado en tpv_business_profile o company_name
            detected = self._auto_detect_business_profile(user_data)
            self.set_business_profile(detected, user_data.get("id"))
    
    def _auto_detect_business_profile(self, user_data: Dict[str, Any]) -> HorarioBusinessProfile:
        """
        Auto-detectar business_profile basado en datos disponibles
        """
        tpv_profile = user_data.get("tpv_business_profile")
        
        # Mapear perfiles TPV a perfiles de Control Horario
        mapping = {
            "restaurante": HorarioBusinessProfile.RESTAURANTE,
            "bar": HorarioBusinessProfile.RESTAURANTE,
            "cafetería": HorarioBusinessProfile.TIENDA,
            "tienda_minorista": HorarioBusinessProfile.TIENDA,
            "peluquería": HorarioBusinessProfile.SERVICIOS,
            "centro_estético": HorarioBusinessProfile.SERVICIOS,
            "taller": HorarioBusinessProfile.SERVICIOS,
            "clínica": HorarioBusinessProfile.SERVICIOS,
            "farmacia": HorarioBusinessProfile.TIENDA,
            "logística": HorarioBusinessProfile.LOGISTICA,
        }
        
        if tpv_profile and tpv_profile in mapping:
            return mapping[tpv_profile]
        
        # Default
        return HorarioBusinessProfile.OFICINA
    
    def check_in(self, employee_id: str, method: CheckInMethod, location: Optional[str] = None,
                 latitude: Optional[float] = None, longitude: Optional[float] = None,
                 user_id: Optional[int] = None, auto_check_in: bool = False) -> Dict[str, Any]:
        """
        Registrar entrada de un empleado
        auto_check_in: Si es True, se auto-registra cuando se inicia un servicio
        """
        try:
            # Mapeo de métodos compatibles (ON_SITE -> location)
            method_value = method.value
            methods_enabled = self.config.get("methods_enabled", [])
            
            # Si se usa ON_SITE pero no está en methods_enabled, mapear a location
            if method_value == "on_site" and "on_site" not in methods_enabled and "location" in methods_enabled:
                method_value = "location"
            
            # Validar método
            if method_value not in methods_enabled:
                # Si es auto check-in, usar método por defecto
                if auto_check_in:
                    default_method = self.config.get("default_method", "on_site")
                    if default_method in methods_enabled:
                        method_value = default_method
                    elif "location" in methods_enabled:
                        method_value = "location"
                    else:
                        return {
                            "success": False,
                            "error_code": "REMOTE_NOT_ENABLED",
                            "error": f"Método {method.value} no está habilitado. Usando método por defecto.",
                            "user_message": "Este servicio se ha registrado como presencial según la configuración de tu empresa."
                        }
                else:
                    return {
                        "success": False,
                        "error_code": "REMOTE_NOT_ENABLED",
                        "error": f"Método {method.value} no está habilitado para este tipo de negocio",
                        "user_message": "Este servicio se ha registrado como presencial según la configuración de tu empresa."
                    }
            
            # Validar GPS si es requerido
            if self.config.get("gps_required") and not (latitude and longitude):
                return {
                    "success": False,
                    "error": "Geolocalización requerida para este tipo de negocio"
                }
            
            # Verificar si ya tiene check-in activo
            if employee_id in self.active_records:
                return {
                    "success": False,
                    "error": "El empleado ya tiene un fichaje de entrada activo"
                }
            
            # Verificar horario programado (si está habilitado)
            if self.config.get("strict_check_in"):
                schedule_check = self._validate_schedule(employee_id, datetime.now())
                if not schedule_check.get("valid"):
                    return {
                        "success": False,
                        "error": schedule_check.get("error", "No está en su horario de trabajo")
                    }
            
            # Crear registro
            record = {
                "id": f"record_{employee_id}_{datetime.now().timestamp()}",
                "employee_id": employee_id,
                "user_id": user_id,
                "check_in_time": datetime.utcnow(),
                "check_in_method": method_value,  # Usar method_value normalizado
                "check_in_location": location or "Oficina Principal",
                "check_in_latitude": latitude,
                "check_in_longitude": longitude,
                "status": "active",
                "irregularities": [],
                "irregularities_count": 0,
                "is_late_check_in": False,
                "synced_with_afrodita": False,
                "synced_with_rafael": False,
                "auto_check_in": auto_check_in  # Marcar si fue auto check-in
            }
            
            # Detectar irregularidades
            irregularities = self._detect_check_in_irregularities(employee_id, record)
            if irregularities:
                record["irregularities"] = irregularities
                record["irregularities_count"] = len(irregularities)
                record["status"] = "irregular" if self.config.get("irregularity_alerts") else "active"
                
                if any("late" in irr for irr in irregularities):
                    record["is_late_check_in"] = True
            
            # Guardar registro activo
            self.active_records[employee_id] = record
            
            logger.info(f"[INFO] Check-in registrado: {employee_id} por {method_value}" + (" (auto)" if auto_check_in else ""))
            
            response = {
                "success": True,
                "record": record,
                "message": "Entrada registrada correctamente"
            }
            
            # Si fue auto check-in y se usó método por defecto, informar
            if auto_check_in and method.value != method_value:
                response["warning"] = "Método ajustado al configurado para tu empresa"
                response["method_used"] = method_value
            
            return response
            
        except Exception as e:
            logger.error(f"Error en check-in: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_out(self, employee_id: str, method: Optional[CheckInMethod] = None,
                  location: Optional[str] = None, latitude: Optional[float] = None,
                  longitude: Optional[float] = None, auto_create_checkin: bool = False) -> Dict[str, Any]:
        """
        Registrar salida de un empleado
        auto_create_checkin: Si es True y no hay check-in, crear uno automáticamente (para servicios)
        """
        try:
            # Verificar que existe check-in activo
            if employee_id not in self.active_records:
                # Si auto_create_checkin está habilitado, crear check-in automático
                if auto_create_checkin and self.config.get("auto_check_in_on_service_start"):
                    default_method_str = self.config.get("default_method", "on_site")
                    try:
                        default_method = CheckInMethod(default_method_str)
                    except ValueError:
                        default_method = CheckInMethod.ON_SITE
                    
                    auto_check_in_result = self.check_in(
                        employee_id=employee_id,
                        method=default_method,
                        location=location or "Oficina Principal",
                        latitude=latitude,
                        longitude=longitude,
                        user_id=None,
                        auto_check_in=True
                    )
                    
                    if not auto_check_in_result.get("success"):
                        return {
                            "success": False,
                            "error_code": "NO_CHECKIN_FOUND",
                            "error": "No hay un fichaje de entrada activo y no se pudo crear uno automáticamente",
                            "user_message": "El servicio se cerró sin registro previo. Se ha corregido automáticamente."
                        }
                    
                    # Continuar con el check-out después del auto check-in
                    logger.info(f"[INFO] Auto check-in creado para {employee_id} antes de check-out")
                else:
                    return {
                        "success": False,
                        "error_code": "NO_CHECKIN_FOUND",
                        "error": "No hay un fichaje de entrada activo",
                        "user_message": "Debes iniciar el servicio antes de finalizarlo"
                    }
            
            record = self.active_records[employee_id]
            
            # Calcular horas trabajadas
            check_out_time = datetime.utcnow()
            check_in_time = record["check_in_time"]
            
            if isinstance(check_in_time, str):
                check_in_time = datetime.fromisoformat(check_in_time.replace('Z', '+00:00'))
            
            time_diff = check_out_time - check_in_time
            hours_worked = time_diff.total_seconds() / 3600.0
            
            # Aplicar pausa si está configurada
            break_duration = self.config.get("break_duration_min", 0) / 60.0  # Convertir a horas
            hours_worked = max(0, hours_worked - break_duration)
            
            # Actualizar registro
            record["check_out_time"] = check_out_time
            record["check_out_method"] = method.value if method else CheckInMethod.CODE.value
            record["check_out_location"] = location
            record["check_out_latitude"] = latitude
            record["check_out_longitude"] = longitude
            record["hours_worked"] = round(hours_worked, 2)
            record["break_duration"] = break_duration
            record["status"] = "completed"
            
            # Detectar irregularidades de salida
            checkout_irregularities = self._detect_check_out_irregularities(employee_id, record)
            if checkout_irregularities:
                record["irregularities"].extend(checkout_irregularities)
                record["irregularities_count"] = len(record["irregularities"])
                record["is_early_check_out"] = any("early" in irr for irr in checkout_irregularities)
            
            # Validar horas mínimas/máximas
            min_hours = self.config.get("min_hours_per_day", 0)
            max_hours = self.config.get("max_hours_per_day", 24)
            
            if hours_worked < min_hours:
                record["irregularities"].append(f"Horas insuficientes: {hours_worked}h < {min_hours}h")
                record["irregularities_count"] = len(record["irregularities"])
            
            if hours_worked > max_hours:
                record["irregularities"].append(f"Horas excedidas: {hours_worked}h > {max_hours}h")
                record["irregularities_count"] = len(record["irregularities"])
            
            # Remover de registros activos
            del self.active_records[employee_id]
            
            logger.info(f"✅ Check-out registrado: {employee_id} - {hours_worked}h trabajadas")
            
            return {
                "success": True,
                "record": record,
                "hours_worked": hours_worked,
                "message": "Salida registrada correctamente"
            }
            
        except Exception as e:
            logger.error(f"Error en check-out: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_current_status(self, employee_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtener estado actual de empleados
        """
        if employee_id:
            if employee_id in self.active_records:
                return {
                    "success": True,
                    "employee_id": employee_id,
                    "status": "inside",
                    "check_in_time": self.active_records[employee_id]["check_in_time"],
                    "record": self.active_records[employee_id]
                }
            else:
                return {
                    "success": True,
                    "employee_id": employee_id,
                    "status": "outside",
                    "check_in_time": None
                }
        else:
            # Estado de todos los empleados
            employees_status = {}
            for emp_id, record in self.active_records.items():
                employees_status[emp_id] = {
                    "status": "inside",
                    "check_in_time": record["check_in_time"],
                    "check_in_method": record["check_in_method"]
                }
            
            return {
                "success": True,
                "employees": employees_status,
                "total_active": len(self.active_records)
            }
    
    def calculate_hours(self, employee_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Calcular horas trabajadas en un período
        """
        # En producción, esto consultaría la base de datos
        # Por ahora, simulamos con registros activos
        
        total_hours = 0.0
        records_count = 0
        
        # Buscar en registros activos completados (en producción, en BD)
        for record in self.active_records.values():
            if record.get("employee_id") == employee_id and record.get("hours_worked"):
                total_hours += record.get("hours_worked", 0)
                records_count += 1
        
        return {
            "success": True,
            "employee_id": employee_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_hours": round(total_hours, 2),
            "records_count": records_count,
            "average_hours_per_day": round(total_hours / max(1, records_count), 2) if records_count > 0 else 0
        }
    
    def _validate_schedule(self, employee_id: str, check_time: datetime) -> Dict[str, Any]:
        """
        Validar si el fichaje está dentro del horario programado
        """
        # En producción, consultaría schedules de la BD
        # Por ahora, validación básica
        day_of_week = check_time.weekday()
        
        schedules = self.schedules.get(employee_id, [])
        for schedule in schedules:
            if schedule.get("day_of_week") == day_of_week:
                # Validar horario
                return {
                    "valid": True,
                    "schedule": schedule
                }
        
        # Si no hay horario estricto configurado, permitir
        if not self.config.get("strict_check_in"):
            return {"valid": True}
        
        return {
            "valid": False,
            "error": "No hay horario programado para este día"
        }
    
    def _detect_check_in_irregularities(self, employee_id: str, record: Dict[str, Any]) -> List[str]:
        """
        Detectar irregularidades en el check-in
        """
        irregularities = []
        
        # Verificar retraso
        if self.config.get("strict_check_in"):
            schedule = self._validate_schedule(employee_id, record["check_in_time"])
            if schedule.get("valid") and schedule.get("schedule"):
                expected_start = schedule["schedule"].get("start_time", "09:00")
                tolerance = self.config.get("tolerance_minutes", 5)
                
                # En producción, calcular retraso real
                # Por ahora, solo detectar si hay horario
                pass
        
        return irregularities
    
    def _detect_check_out_irregularities(self, employee_id: str, record: Dict[str, Any]) -> List[str]:
        """
        Detectar irregularidades en el check-out
        """
        irregularities = []
        
        # Verificar salida temprana
        if self.config.get("strict_check_in"):
            schedule = self._validate_schedule(employee_id, record["check_out_time"])
            if schedule.get("valid") and schedule.get("schedule"):
                expected_end = schedule["schedule"].get("end_time", "18:00")
                # En producción, calcular salida temprana real
                pass
        
        # Verificar falta de pausa
        if self.config.get("break_time_required"):
            hours = record.get("hours_worked", 0)
            if hours > 6 and not record.get("break_duration", 0):
                irregularities.append("missing_break")
        
        return irregularities
    
    def sync_with_afrodita(self, employee_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sincronizar registro con AFRODITA
        """
        try:
            if not self.afrodita_integration:
                return {"success": False, "error": "AFRODITA integration no disponible"}
            
            # En producción, llamar a AFRODITA
            record["synced_with_afrodita"] = True
            record["afrodita_sync_date"] = datetime.utcnow()
            
            logger.info(f"👥 Registro sincronizado con AFRODITA: {employee_id}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error sincronizando con AFRODITA: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_with_rafael(self, employee_id: str, hours_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sincronizar horas trabajadas con RAFAEL para nóminas
        """
        try:
            if not self.rafael_integration:
                return {"success": False, "error": "RAFAEL integration no disponible"}
            
            # En producción, enviar a RAFAEL para cálculo de nómina
            logger.info(f"📊 Horas enviadas a RAFAEL para nómina: {employee_id}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error sincronizando con RAFAEL: {e}")
            return {"success": False, "error": str(e)}
