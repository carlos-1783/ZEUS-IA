"""
👥 AFRODITA - Recursos Humanos y Logística
Gestión de personal, horarios, rutas, fichajes y bienestar del equipo
"""
from .base_agent import BaseAgent
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class Afrodita(BaseAgent):
    """
    AFRODITA - Agente de RRHH y Logística
    
    Responsabilidades:
    - Gestión de empleados (alta, baja, datos)
    - Control de horarios y fichajes
    - Gestión de vacaciones y ausencias
    - Nóminas y beneficios
    - Preparación de rutas de reparto
    - Gestión de flotas
    - Logística y entregas
    - Bienestar del equipo
    """
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        
        # Cargar config de AFRODITA si existe, sino usar defaults
        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            afrodita_config = config["zeus_prime_v1"]["agents"].get("AFRODITA", {})
            system_prompt = afrodita_config.get("prompt", None)
            temperature = afrodita_config.get("parameters", {}).get("temperature", 0.7)
            max_tokens = afrodita_config.get("parameters", {}).get("max_tokens", 2000)
        except:
            system_prompt = None
            temperature = 0.7
            max_tokens = 2000
        
        super().__init__(
            name="AFRODITA",
            role="HR & Logistics Manager",
            system_prompt=system_prompt or """Eres AFRODITA, la agente de Recursos Humanos y Logística de ZEUS-IA.

Tu nombre proviene de la diosa griega del amor y la armonía, porque tu misión es cuidar del activo más valioso de cualquier empresa: LAS PERSONAS.

## TU ROL:
Eres la encargada de gestionar TODO lo relacionado con el equipo humano y su coordinación:
- Recursos Humanos (fichajes, horarios, vacaciones, nóminas)
- Logística (rutas, entregas, gestión de flotas)
- Bienestar del equipo (clima laboral, resolución de conflictos)

## TU PERSONALIDAD:
- Empática y cercana (pero profesional)
- Organizada y eficiente
- Proactiva en detectar problemas antes de que escalen
- Equilibras lo humano con lo operativo

## TUS RESPONSABILIDADES:

### 1. GESTIÓN DE EMPLEADOS:
- Onboarding de nuevos empleados
- Actualización de datos personales
- Gestión de documentación (contratos, nóminas, certificados)
- Offboarding cuando alguien deja la empresa

### 2. CONTROL HORARIO:
- Registro de fichajes (entrada/salida)
- Cálculo de horas trabajadas
- Gestión de horas extra
- Detección de irregularidades (retrasos, ausencias)

### 3. VACACIONES Y AUSENCIAS:
- Solicitud y aprobación de vacaciones
- Gestión de bajas médicas
- Calendario de ausencias
- Planificación de cobertura

### 4. NÓMINAS:
- Preparación de datos para nómina
- Cálculo de salarios (base + extras + deducciones)
- Generación de recibos de pago
- Coordinación con RAFAEL para temas fiscales

### 5. LOGÍSTICA Y RUTAS:
- Optimización de rutas de reparto
- Asignación de vehículos y conductores
- Seguimiento de entregas en tiempo real
- Gestión de incidencias logísticas

### 6. GESTIÓN DE FLOTAS:
- Mantenimiento de vehículos
- Control de combustible
- Revisiones técnicas
- Gestión de seguros

### 7. BIENESTAR DEL EQUIPO:
- Detección de problemas de clima laboral
- Sugerencias de mejoras organizativas
- Mediación en conflictos
- Promoción de cultura empresarial positiva

## CÓMO TRABAJAS:

### Con empleados:
- Lenguaje cercano y amable
- Respuestas claras y rápidas
- Proactividad (recordatorios, avisos)
- Confidencialidad total

### Con gestión:
- Informes claros y visuales
- Alertas de situaciones críticas
- Recomendaciones basadas en datos
- Automatización de tareas repetitivas

### Con otros agentes:
- RAFAEL: Coordinas para nóminas, impuestos laborales, Seguridad Social
- JUSTICIA: Consultas sobre contratos, legislación laboral, despidos
- THALOS: Gestión de accesos, seguridad de datos personales
- ZEUS CORE: Reportas métricas y solicitas decisiones estratégicas

## EJEMPLOS DE INTERACCIÓN:

### Empleado pregunta:
"¿Cuántas vacaciones me quedan?"
→ Tú: "Hola Juan 👋 Te quedan 12 días de vacaciones este año. ¿Quieres solicitar algunos días? Te muestro el calendario de disponibilidad del equipo."

### Gestor pregunta:
"¿Quién puede cubrir a María mañana?"
→ Tú: "María está de baja mañana. Analizo disponibilidad... Pablo está disponible y tiene experiencia en ese puesto. ¿Quieres que le notifique?"

### Proactivo:
"⚠️ ALERTA: El vehículo V-003 tiene revisión técnica el 15/11. ¿Programo cita en el taller?"

## MÉTRICAS QUE MANEJAS:
- Tasa de absentismo
- Horas extra por empleado
- Rotación de personal
- Satisfacción del equipo (NPS interno)
- Eficiencia logística (entregas a tiempo)
- Coste por ruta
- Kilometraje por vehículo

## TU FILOSOFÍA:
"Una empresa no son solo procesos y beneficios. Una empresa son PERSONAS. Y cuando las personas están bien, TODO funciona mejor."

## IMPORTANTE:
- NUNCA compartes datos personales de empleados sin autorización
- SIEMPRE cumples con GDPR y legislación laboral
- Si hay un conflicto grave, ESCALAS a ZEUS CORE
- Si hay dudas legales, CONSULTAS con JUSTICIA
- Si hay temas fiscales (nóminas, IRPF), COORDINAS con RAFAEL

Habla siempre en español (España), de forma natural, profesional pero cercana.

Eres la voz humana de ZEUS-IA. El corazón del sistema. 💙""",
            temperature=temperature,
            max_tokens=max_tokens,
            hitl_threshold=0.75
        )
        
        # Configurar dominio
        self.domain = "Recursos Humanos, Logística, Gestión de Personal"
        
        # Cargar capacidades desde config
        try:
            self.capabilities = afrodita_config.get("parameters", {}).get("capabilities", [])
        except:
            self.capabilities = []
        
        # Integración TPV
        self.tpv_integration_enabled = "integracion_TPV_sync_employees" in self.capabilities
        
        print(f"👥 AFRODITA inicializada - Dominio: {self.domain}")
        if self.tpv_integration_enabled:
            print(f"💳 Integración TPV habilitada: sync_employees, role_permissions")

    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud relacionada con RRHH o Logística
        
        Args:
            context: Contexto con información de la solicitud
            
        Returns:
            Respuesta estructurada de AFRODITA
        """
        user_message = context.get("user_message", "")
        channel = context.get("channel", "chat")
        priority = context.get("priority", "normal")
        
        # Si es comunicación entre agentes, procesar directamente
        if context.get("inter_agent_communication"):
            enhanced_message = user_message
        else:
            enhanced_message = user_message
            
            # Detectar si necesita ayuda de otros agentes
            needs_fiscal_help = any(kw in user_message.lower() for kw in [
                "fiscal", "impuesto", "iva", "irpf", "hacienda", "nómina", "seguridad social"
            ])
            needs_legal_help = any(kw in user_message.lower() for kw in [
                "legal", "contrato", "despido", "baja", "gdpr", "privacidad"
            ])
            
            # Si necesita ayuda fiscal, solicitar a RAFAEL
            if needs_fiscal_help and self.zeus_core_ref:
                print(f"📡 [AFRODITA] Detecté necesidad de ayuda fiscal, consultando a RAFAEL...")
                fiscal_response = self.request_agent_help(
                    "RAFAEL",
                    f"AFRODITA necesita información fiscal para: {user_message}",
                    context
                )
                if fiscal_response and fiscal_response.get("success"):
                    enhanced_message += f"\n\n[Información de RAFAEL]: {fiscal_response.get('content', '')[:500]}"
            
            # Si necesita ayuda legal, solicitar a JUSTICIA
            if needs_legal_help and self.zeus_core_ref:
                print(f"📡 [AFRODITA] Detecté necesidad de ayuda legal, consultando a JUSTICIA...")
                legal_response = self.request_agent_help(
                    "JUSTICIA",
                    f"AFRODITA necesita información legal para: {user_message}",
                    context
                )
                if legal_response and legal_response.get("success"):
                    enhanced_message += f"\n\n[Información de JUSTICIA]: {legal_response.get('content', '')[:500]}"
        
        # Analizar tipo de consulta
        query_type = self._classify_query(user_message)
        
        try:
            decision = self.make_decision(enhanced_message, additional_context=context)
            decision["query_type"] = query_type
            decision["channel"] = channel
            decision["priority"] = priority
            metadata = decision.get("metadata", {})
            metadata.update(
                {
                    "domain": self.domain,
                    "requires_approval": query_type in ["nomina", "despido", "contrato"],
                    "escalate_to_zeus": False,
                }
            )
            decision["metadata"] = metadata
            return decision
            
        except Exception:
            logger.exception("[AFRODITA] error procesando la solicitud")
            return {
                "success": False,
                "agent": self.name,
                "error": "internal_error",
                "fallback_message": "Lo siento, tuve un problema procesando tu solicitud de RRHH/Logística. Por favor, intenta nuevamente."
            }
    
    def _classify_query(self, message: str) -> str:
        """Clasificar tipo de consulta de RRHH/Logística"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["vacaciones", "dias libres", "ausencia"]):
            return "vacaciones"
        elif any(word in message_lower for word in ["fichaje", "horario", "entrada", "salida"]):
            return "fichaje"
        elif any(word in message_lower for word in ["nomina", "salario", "pago", "sueldo"]):
            return "nomina"
        elif any(word in message_lower for word in ["ruta", "reparto", "entrega", "logistica"]):
            return "logistica"
        elif any(word in message_lower for word in ["vehiculo", "flota", "mantenimiento"]):
            return "flota"
        elif any(word in message_lower for word in ["contrato", "alta", "baja", "empleado"]):
            return "contrato"
        elif any(word in message_lower for word in ["conflicto", "problema", "queja"]):
            return "conflicto"
        else:
            return "general"
    
    def get_employee_info(self, employee_id: str) -> Dict[str, Any]:
        """Obtener información de un empleado"""
        # TODO: Integrar con base de datos de empleados
        return {
            "id": employee_id,
            "name": "Pendiente de implementar",
            "position": "",
            "department": "",
            "hire_date": "",
            "vacation_days_remaining": 0
        }
    
    def calculate_payroll(self, employee_id: str, month: int, year: int) -> Dict[str, Any]:
        """Calcular nómina de un empleado"""
        # TODO: Implementar lógica de cálculo de nómina
        return {
            "employee_id": employee_id,
            "period": f"{month}/{year}",
            "base_salary": 0,
            "overtime": 0,
            "bonuses": 0,
            "deductions": 0,
            "net_salary": 0,
            "status": "pending_calculation"
        }
    
    def optimize_route(self, deliveries: list, start_location: str) -> Dict[str, Any]:
        """Optimizar ruta de reparto"""
        # TODO: Implementar algoritmo de optimización de rutas
        return {
            "start": start_location,
            "stops": len(deliveries),
            "optimized_order": [],
            "estimated_distance_km": 0,
            "estimated_time_minutes": 0,
            "status": "pending_optimization"
        }
    
    def sync_tpv_employee(self, employee_id: str, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sincronizar datos de empleado con TPV
        
        Args:
            employee_id: ID del empleado
            ticket_data: Datos del ticket del TPV
        
        Returns:
            Dict con resultado de sincronización
        """
        if not self.tpv_integration_enabled:
            return {
                "success": False,
                "error": "Integración TPV no habilitada en AFRODITA"
            }
        
        try:
            # Validar permisos del empleado
            employee_permissions = self._get_employee_permissions(employee_id)
            
            # Validar que el empleado tiene permisos para realizar ventas
            if not employee_permissions.get("can_sell", False):
                return {
                    "success": False,
                    "error": f"Empleado {employee_id} no tiene permisos para realizar ventas"
                }
            
            # Registrar venta en historial del empleado
            sale_record = {
                "employee_id": employee_id,
                "sale_date": ticket_data.get("date"),
                "sale_total": ticket_data.get("totals", {}).get("total", 0),
                "items_sold": ticket_data.get("totals", {}).get("items_count", 0),
                "terminal_id": ticket_data.get("terminal_id"),
                "payment_method": ticket_data.get("payment_method")
            }
            
            # Sincronizar con sistema de RRHH
            sync_result = {
                "employee_id": employee_id,
                "sale_recorded": True,
                "role_permissions_validated": True,
                "permissions": employee_permissions,
                "sale_record": sale_record
            }
            
            logger.info(f"👥 AFRODITA sincronizó empleado TPV: {employee_id} - Venta: €{sale_record['sale_total']:.2f}")
            
            return {
                "success": True,
                "sync_result": sync_result
            }
            
        except Exception as e:
            logger.error(f"Error sincronizando empleado TPV en AFRODITA: {e}")
            return {
                "success": False,
                "error": "internal_error"
            }
    
    def _get_employee_permissions(self, employee_id: str) -> Dict[str, Any]:
        """Obtener permisos del empleado"""
        # En una implementación completa, esto consultaría la BD
        # Por ahora retornamos permisos por defecto
        return {
            "can_sell": True,
            "can_refund": False,
            "can_close_register": False,
            "can_view_reports": False,
            "role": "employee"
        }

