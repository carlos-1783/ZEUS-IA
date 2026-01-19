"""
Endpoints para el módulo de Control Horario Universal
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import logging

from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from services.control_horario_service import (
    ControlHorarioService,
    HorarioBusinessProfile,
    CheckInMethod
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Instancia singleton del servicio
control_horario_service = ControlHorarioService()


# Modelos Pydantic
class CheckInRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    method: str = Field(..., description="Método de fichaje: face, qr, code, location, remote")
    location: Optional[str] = Field(None, description="Ubicación del fichaje")
    latitude: Optional[float] = Field(None, description="Latitud GPS")
    longitude: Optional[float] = Field(None, description="Longitud GPS")


class CheckOutRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    method: Optional[str] = Field(None, description="Método de fichaje: face, qr, code, location, remote")
    location: Optional[str] = Field(None, description="Ubicación del fichaje")
    latitude: Optional[float] = Field(None, description="Latitud GPS")
    longitude: Optional[float] = Field(None, description="Longitud GPS")


class SetBusinessProfileRequest(BaseModel):
    business_profile: str = Field(..., description="Perfil de negocio para control horario")


class CalculateHoursRequest(BaseModel):
    employee_id: str
    start_date: str  # ISO format
    end_date: str  # ISO format


async def _get_control_horario_info(current_user: User):
    """Función auxiliar para obtener información del Control Horario"""
    from sqlalchemy.orm import Session
    from app.db.base import SessionLocal
    
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Cargar business_profile del usuario
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            user_data = {
                "id": user.id,
                "control_horario_business_profile": getattr(user, 'control_horario_business_profile', None),
                "tpv_business_profile": getattr(user, 'tpv_business_profile', None),
                "company_name": getattr(user, 'company_name', None)
            }
            try:
                control_horario_service.load_user_profile(user_data)
            except Exception as e:
                logger.warning(f"Error cargando perfil de usuario: {e}")
                if not control_horario_service.business_profile and not is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
                elif not control_horario_service.business_profile and is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
        else:
            if not control_horario_service.business_profile:
                user_data = {
                    "id": current_user.id,
                    "company_name": getattr(current_user, 'company_name', None)
                }
                control_horario_service.load_user_profile(user_data)
                if not control_horario_service.business_profile and not is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
                elif not control_horario_service.business_profile and is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
    except Exception as e:
        logger.error(f"Error cargando perfil de usuario: {e}")
        if not control_horario_service.business_profile:
            control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
    finally:
        db.close()
    
    config = control_horario_service.config if control_horario_service.business_profile else {}
    
    # Para superusuarios, asegurar configuración completa
    if is_superuser and not config:
        config = {
            "strict_check_in": True,
            "gps_required": False,
            "multiple_shifts_per_day": True,
            "break_time_required": True,
            "auto_check_out": False,
            "irregularity_alerts": True,
            "methods_enabled": ["face", "qr", "code", "location", "remote"],
            "location_tracking": False,
            "remote_allowed": True,
            "flexible_hours": True,
            "superuser_override": True
        }
    
    return {
        "success": True,
        "service": "Control Horario Universal Enterprise",
        "version": "1.0.0",
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active
        },
        "business_profile": control_horario_service.business_profile.value if control_horario_service.business_profile else None,
        "config": config,
        "active_records_count": len(control_horario_service.active_records),
        "employees_count": len(control_horario_service.employees),
        "integrations": {
            "afrodita": control_horario_service.afrodita_integration is not None,
            "rafael": control_horario_service.rafael_integration is not None,
            "tpv": control_horario_service.tpv_integration is not None
        }
    }


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=True)
async def get_control_horario_root(
    current_user: User = Depends(get_current_active_user)
):
    """Endpoint raíz del Control Horario - Devuelve información básica"""
    return await _get_control_horario_info(current_user)


@router.get("/status")
async def get_control_horario_status(
    employee_id: Optional[str] = Query(None, description="ID del empleado (opcional)"),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener estado actual del Control Horario"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Cargar perfil si no está cargado
    if not control_horario_service.business_profile:
        await _get_control_horario_info(current_user)
    
    # Obtener estado
    status_data = control_horario_service.get_current_status(employee_id)
    
    return {
        "success": True,
        "business_profile": control_horario_service.business_profile.value if control_horario_service.business_profile else None,
        "config": control_horario_service.config if control_horario_service.business_profile else {},
        "status": status_data,
        "is_superuser": is_superuser
    }


@router.post("/check-in")
async def check_in(
    request: CheckInRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Registrar entrada de un empleado"""
    try:
        # Cargar perfil si no está cargado
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user)
        
        # Validar método
        try:
            method = CheckInMethod(request.method.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Método inválido: {request.method}. Métodos válidos: face, qr, code, location, remote"
            )
        
        # Registrar check-in
        result = control_horario_service.check_in(
            employee_id=request.employee_id,
            method=method,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
            user_id=current_user.id
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Error al registrar entrada")
            )
        
        # Sincronizar con AFRODITA si está disponible
        if control_horario_service.afrodita_integration:
            control_horario_service.sync_with_afrodita(request.employee_id, result["record"])
        
        logger.info(f"✅ Check-in registrado: {request.employee_id}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en check-in: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )


@router.post("/check-out")
async def check_out(
    request: CheckOutRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Registrar salida de un empleado"""
    try:
        # Cargar perfil si no está cargado
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user)
        
        # Validar método si se proporciona
        method = None
        if request.method:
            try:
                method = CheckInMethod(request.method.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Método inválido: {request.method}"
                )
        
        # Registrar check-out
        result = control_horario_service.check_out(
            employee_id=request.employee_id,
            method=method,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Error al registrar salida")
            )
        
        # Sincronizar con RAFAEL para cálculo de nóminas
        if control_horario_service.rafael_integration and result.get("hours_worked"):
            control_horario_service.sync_with_rafael(
                request.employee_id,
                {
                    "hours_worked": result.get("hours_worked"),
                    "date": datetime.utcnow().date().isoformat(),
                    "record": result.get("record")
                }
            )
        
        # Sincronizar con AFRODITA
        if control_horario_service.afrodita_integration:
            control_horario_service.sync_with_afrodita(request.employee_id, result["record"])
        
        logger.info(f"✅ Check-out registrado: {request.employee_id} - {result.get('hours_worked', 0)}h")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en check-out: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )


@router.get("/employees")
async def get_employees(
    current_user: User = Depends(get_current_active_user)
):
    """Listar empleados con estado actual"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user)
        
        status_data = control_horario_service.get_current_status()
        
        return {
            "success": True,
            "employees": status_data.get("employees", {}),
            "total_active": status_data.get("total_active", 0)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo empleados: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/calculate-hours")
async def calculate_hours(
    request: CalculateHoursRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Calcular horas trabajadas en un período"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user)
        
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        result = control_horario_service.calculate_hours(
            employee_id=request.employee_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculando horas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/set-business-profile")
async def set_business_profile(
    request: SetBusinessProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Establecer business_profile para Control Horario"""
    try:
        profile_str = request.business_profile.lower()
        
        try:
            profile = HorarioBusinessProfile(profile_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Perfil inválido: {profile_str}. Perfiles válidos: {[p.value for p in HorarioBusinessProfile]}"
            )
        
        # Actualizar en base de datos
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            try:
                setattr(user, 'control_horario_business_profile', profile.value)
                db.commit()
                logger.info(f"✅ Business profile actualizado: {profile.value}")
            except Exception as e:
                logger.warning(f"Error actualizando control_horario_business_profile: {e}")
                db.rollback()
        
        # Actualizar servicio
        control_horario_service.set_business_profile(profile, current_user.id)
        
        return {
            "success": True,
            "message": f"Business profile actualizado a: {profile.value}",
            "business_profile": profile.value,
            "config": control_horario_service.config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estableciendo business profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/reports")
async def get_reports(
    employee_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener reportes de asistencia"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user)
        
        # Por ahora, devolver datos básicos
        # En producción, consultaría la base de datos
        
        status_data = control_horario_service.get_current_status(employee_id)
        
        return {
            "success": True,
            "reports": {
                "current_status": status_data,
                "active_records": len(control_horario_service.active_records)
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo reportes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
