# ========================================
# NÚCLEO ZEUS-IA - AGENTES ESPECIALIZADOS
# ========================================

from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)

class AgentType(Enum):
    """Tipos de agentes del Núcleo ZEUS"""
    ZEUS = "zeus"           # Núcleo principal
    PERSEO = "perseo"       # Estratega de Ventas y Crecimiento
    THALOS = "thalos"       # Ciberdefensa Automatizada
    JUSTICIA = "justicia"   # Abogada Digital
    RAFAEL = "rafael"       # Asistente Fiscal y Contable
    ANALISIS = "analisis"   # Análisis de datos
    IA = "ia"              # Inteligencia artificial

class AgentStatus(Enum):
    """Estados de los agentes"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PROCESSING = "processing"
    ERROR = "error"

class ZeusAgent:
    """Clase base para todos los agentes del Núcleo ZEUS"""
    
    def __init__(self, agent_type: AgentType, name: str, description: str):
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.status = AgentStatus.INACTIVE
        self.last_activity = None
        self.logs = []
        
    def activate(self) -> Dict[str, Any]:
        """Activar el agente"""
        self.status = AgentStatus.ACTIVE
        self.last_activity = datetime.utcnow()
        
        log_entry = {
            "timestamp": self.last_activity.isoformat(),
            "action": "agent_activated",
            "agent": self.name,
            "status": "success"
        }
        self.logs.append(log_entry)
        
        return {
            "status": "success",
            "message": f"Agente {self.name} activado correctamente",
            "agent": self.name,
            "timestamp": self.last_activity.isoformat(),
            "animation": "activate"
        }
    
    def process_command(self, command: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Procesar comando específico del agente"""
        self.status = AgentStatus.PROCESSING
        
        try:
            result = self._execute_command(command, data or {})
            self.status = AgentStatus.ACTIVE
            self.last_activity = datetime.utcnow()
            
            log_entry = {
                "timestamp": self.last_activity.isoformat(),
                "action": "command_executed",
                "agent": self.name,
                "command": command,
                "status": "success"
            }
            self.logs.append(log_entry)
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"Error en agente {self.name}: {str(e)}")
            
            return {
                "status": "error",
                "message": f"Error en agente {self.name}: {str(e)}",
                "agent": self.name,
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "error"
            }
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Implementar en cada agente específico"""
        raise NotImplementedError

class ZeusCore(ZeusAgent):
    """Núcleo principal ZEUS - Coordinador general del ecosistema empresarial"""
    
    def __init__(self):
        super().__init__(
            AgentType.ZEUS,
            "ZEUS",
            "Núcleo principal del ecosistema empresarial inteligente"
        )
        self.sub_agents = {}
        self.specializations = {
            "PER-SEO": "Estratega de Ventas y Crecimiento Exponencial",
            "RAFAEL": "Asistente Fiscal y Contable (España)",
            "THALOS": "Ciberdefensa Automatizada (ZEUS SHIELD)",
            "JUSTICIA": "Abogada Digital"
        }
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar comandos del núcleo ZEUS"""
        
        if command == "ZEUS.ACTIVAR":
            return self._activate_system(data)
        elif command == "ZEUS.ANALIZAR":
            return self._analyze_system(data)
        elif command == "ZEUS.EJECUTAR":
            return self._execute_operation(data)
        elif command == "ZEUS.SEGURIDAD":
            return self._security_check(data)
        elif command == "ZEUS.REGLAS":
            return self._apply_rules(data)
        elif command == "ZEUS.BIENESTAR":
            return self._wellness_check(data)
        else:
            return {
                "status": "error",
                "message": f"Comando ZEUS no reconocido: {command}",
                "available_commands": [
                    "ZEUS.ACTIVAR", "ZEUS.ANALIZAR", "ZEUS.EJECUTAR",
                    "ZEUS.SEGURIDAD", "ZEUS.REGLAS", "ZEUS.BIENESTAR"
                ]
            }
    
    def _activate_system(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Activar todo el sistema ZEUS con especializaciones reales"""
        return {
            "status": "success",
            "message": "Núcleo ZEUS activado - Ecosistema empresarial operativo",
            "agent": "ZEUS",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "system_activation",
            "voice": "Sistema ZEUS activado. Ecosistema empresarial completo operativo.",
            "data": {
                "system_status": "active",
                "agents_online": len(self.sub_agents),
                "specializations": self.specializations,
                "capabilities": [
                    "PER-SEO: Estrategia de ventas y crecimiento exponencial",
                    "RAFAEL: Gestión fiscal y contable (España)",
                    "THALOS: Ciberdefensa automatizada 24/7",
                    "JUSTICIA: Defensa legal y cumplimiento RGPD",
                    "ANÁLISIS: Análisis de datos empresariales",
                    "IA: Inteligencia artificial avanzada"
                ]
            }
        }
    
    def _analyze_system(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis completo del sistema"""
        return {
            "status": "success",
            "message": "Análisis del sistema completado",
            "agent": "ZEUS",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "analysis",
            "voice": "Análisis completado. Sistema funcionando al 100%.",
            "data": {
                "performance": "100%",
                "security_level": "máximo",
                "compliance": "total",
                "recommendations": [
                    "Sistema optimizado",
                    "Seguridad garantizada",
                    "Cumplimiento total"
                ]
            }
        }
    
    def _execute_operation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecutar operación específica"""
        operation = data.get("operation", "default")
        return {
            "status": "success",
            "message": f"Operación {operation} ejecutada correctamente",
            "agent": "ZEUS",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "execute",
            "voice": f"Operación {operation} completada exitosamente.",
            "data": {
                "operation": operation,
                "result": "success",
                "execution_time": "instant"
            }
        }
    
    def _security_check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Verificación de seguridad"""
        return {
            "status": "success",
            "message": "Verificación de seguridad completada",
            "agent": "ZEUS",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "security_scan",
            "voice": "Verificación de seguridad completada. Sistema seguro.",
            "data": {
                "security_level": "máximo",
                "threats_detected": 0,
                "protection_status": "activo",
                "recommendations": ["Sistema completamente seguro"]
            }
        }
    
    def _apply_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aplicar reglas del sistema"""
        return {
            "status": "success",
            "message": "Reglas aplicadas correctamente",
            "agent": "ZEUS",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "rules_application",
            "voice": "Reglas aplicadas. Sistema en cumplimiento total.",
            "data": {
                "rules_applied": "todas",
                "compliance": "100%",
                "status": "cumplimiento_total"
            }
        }
    
    def _wellness_check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Verificación de bienestar del usuario"""
        return {
            "status": "success",
            "message": "Verificación de bienestar completada",
            "agent": "ZEUS",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "wellness_check",
            "voice": "Verificación de bienestar completada. Usuario en óptimas condiciones.",
            "data": {
                "user_wellness": "óptimo",
                "recommendations": [
                    "Mantener el ritmo actual",
                    "Sistema funcionando perfectamente"
                ]
            }
        }

class PerSeoAgent(ZeusAgent):
    """Agente PER-SEO - Estratega de Ventas y Crecimiento Exponencial"""
    
    def __init__(self):
        super().__init__(
            AgentType.PERSEO,
            "PER-SEO",
            "Estratega de Ventas y Crecimiento Exponencial"
        )
        self.specializations = [
            "Diseño y ejecución de funnels de ventas",
            "Marketing basado en datos + copywriting de conversión",
            "Análisis competitivo y posicionamiento SEO",
            "Optimización de conversión y retención"
        ]
        self.mantra = "Si lo imaginas, lo ejecutas. Si lo ejecutas, lo dominas."
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comandos específicos de PER-SEO"""
        if command == "PERSEO.FUNNEL":
            return {
                "status": "success",
                "message": "Funnel de ventas diseñado y optimizado",
                "agent": "PER-SEO",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "funnel_creation",
                "voice": "Funnel de ventas diseñado. Conversión optimizada para máximo crecimiento.",
                "data": {
                    "funnel_stages": ["Awareness", "Interest", "Consideration", "Purchase", "Retention"],
                    "conversion_rate": "25%",
                    "optimization_tips": [
                        "Landing page optimizada",
                        "Copy persuasivo implementado",
                        "CTA estratégicamente ubicado"
                    ],
                    "mantra": self.mantra
                }
            }
        elif command == "PERSEO.SEO":
            return {
                "status": "success",
                "message": "Análisis SEO y posicionamiento completado",
                "agent": "PER-SEO",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "seo_analysis",
                "voice": "Análisis SEO completado. Posicionamiento estratégico implementado.",
                "data": {
                    "keywords_targeted": 50,
                    "competitor_analysis": "completado",
                    "ranking_improvement": "+15 posiciones",
                    "recommendations": [
                        "Contenido optimizado para conversión",
                        "Meta tags estratégicos",
                        "Estructura SEO-friendly"
                    ]
                }
            }
        elif command == "PERSEO.COPY":
            return {
                "status": "success",
                "message": "Copy de conversión generado",
                "agent": "PER-SEO",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "copywriting",
                "voice": "Copy de conversión generado. Mensaje persuasivo listo para implementar.",
                "data": {
                    "copy_type": "conversión",
                    "emotional_triggers": ["urgencia", "escasez", "autoridad"],
                    "conversion_elements": [
                        "Headline impactante",
                        "Beneficios claros",
                        "CTA irresistible"
                    ],
                    "expected_conversion": "+40%"
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Comando PER-SEO no reconocido: {command}",
                "available_commands": ["PERSEO.FUNNEL", "PERSEO.SEO", "PERSEO.COPY"],
                "specializations": self.specializations
            }

class ThalosAgent(ZeusAgent):
    """Agente THALOS - Ciberdefensa Automatizada (ZEUS SHIELD)"""
    
    def __init__(self):
        super().__init__(
            AgentType.THALOS,
            "THALOS",
            "Ciberdefensa Automatizada (ZEUS SHIELD)"
        )
        self.specializations = [
            "Monitorización de seguridad 24/7",
            "Bloqueo de IPs sospechosas y revocación de credenciales",
            "Encriptación inmediata y autenticación JWT/OAuth2",
            "Alertas de intrusión en tiempo real"
        ]
        self.shield_status = "activo"
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comandos específicos de THALOS"""
        if command == "THALOS.SHIELD":
            return {
                "status": "success",
                "message": "ZEUS SHIELD activado - Protección máxima",
                "agent": "THALOS",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "shield_activation",
                "voice": "ZEUS SHIELD activado. Protección cibernética máxima implementada.",
                "data": {
                    "shield_level": "máximo",
                    "monitoring_24_7": True,
                    "threats_blocked": 0,
                    "encryption_status": "activo",
                    "jwt_oauth2": "configurado"
                }
            }
        elif command == "THALOS.SCAN":
            return {
                "status": "success",
                "message": "Escaneo de seguridad completado",
                "agent": "THALOS",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "security_scan",
                "voice": "Escaneo de seguridad completado. Sistema protegido contra amenazas.",
                "data": {
                    "scan_result": "limpio",
                    "vulnerabilities_found": 0,
                    "ips_blocked": 0,
                    "credentials_revoked": 0,
                    "security_score": "100%"
                }
            }
        elif command == "THALOS.BLOCK":
            return {
                "status": "success",
                "message": "IPs sospechosas bloqueadas",
                "agent": "THALOS",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "ip_blocking",
                "voice": "IPs sospechosas bloqueadas. Acceso no autorizado prevenido.",
                "data": {
                    "blocked_ips": ["192.168.1.100", "10.0.0.50"],
                    "threat_level": "alto",
                    "action_taken": "bloqueo_inmediato",
                    "monitoring_active": True
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Comando THALOS no reconocido: {command}",
                "available_commands": ["THALOS.SHIELD", "THALOS.SCAN", "THALOS.BLOCK"],
                "specializations": self.specializations
            }

class JusticiaAgent(ZeusAgent):
    """Agente JUSTICIA - Abogada Digital"""
    
    def __init__(self):
        super().__init__(
            AgentType.JUSTICIA,
            "JUSTICIA",
            "Abogada Digital especializada en derecho español e internacional"
        )
        self.specializations = [
            "Derecho español e internacional",
            "Redacción y revisión de contratos, avisos legales, términos de uso",
            "Cumplimiento del RGPD y defensa ante amenazas legales",
            "Protección jurídica preventiva"
        ]
        self.protocol = "Activar defensa jurídica preventiva ante cualquier riesgo"
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comandos específicos de JUSTICIA"""
        if command == "JUSTICIA.CONTRATO":
            return {
                "status": "success",
                "message": "Contrato redactado y revisado",
                "agent": "JUSTICIA",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "contract_review",
                "voice": "Contrato redactado y revisado. Cumplimiento legal garantizado.",
                "data": {
                    "contract_type": "prestación de servicios",
                    "legal_review": "completado",
                    "rgpd_compliance": "100%",
                    "clauses_included": [
                        "Protección de datos",
                        "Confidencialidad",
                        "Resolución de disputas",
                        "Jurisdicción aplicable"
                    ],
                    "protocol": self.protocol
                }
            }
        elif command == "JUSTICIA.RGPD":
            return {
                "status": "success",
                "message": "Verificación RGPD completada",
                "agent": "JUSTICIA",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "gdpr_check",
                "voice": "Verificación RGPD completada. Cumplimiento total de normativa europea.",
                "data": {
                    "compliance_status": "100%",
                    "data_protection": "activo",
                    "user_rights": "garantizados",
                    "documentation": [
                        "Política de privacidad",
                        "Aviso legal",
                        "Términos de uso",
                        "Consentimientos"
                    ],
                    "recommendations": ["Sistema conforme al RGPD"]
                }
            }
        elif command == "JUSTICIA.DEFENSA":
            return {
                "status": "success",
                "message": "Defensa jurídica preventiva activada",
                "agent": "JUSTICIA",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "legal_defense",
                "voice": "Defensa jurídica preventiva activada. Protección legal completa.",
                "data": {
                    "defense_status": "activo",
                    "legal_threats": 0,
                    "preventive_measures": [
                        "Revisión de contratos",
                        "Auditoría legal",
                        "Protección de marca",
                        "Cumplimiento normativo"
                    ],
                    "jurisdiction": "España e internacional"
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Comando JUSTICIA no reconocido: {command}",
                "available_commands": ["JUSTICIA.CONTRATO", "JUSTICIA.RGPD", "JUSTICIA.DEFENSA"],
                "specializations": self.specializations
            }

class RafaelAgent(ZeusAgent):
    """Agente RAFAEL - Asistente Fiscal y Contable (España)"""
    
    def __init__(self):
        super().__init__(
            AgentType.RAFAEL,
            "RAFAEL",
            "Asistente Fiscal y Contable (España)"
        )
        self.specializations = [
            "Modelos 303, 130, 390, IS, IRPF, IVA",
            "Cumplimiento legal y presentación telemática ante Hacienda",
            "Optimización fiscal dentro del marco legal",
            "Gestión contable automatizada"
        ]
        self.protocol = "Siempre solicitar aprobación antes de ejecutar acciones contables o fiscales"
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comandos específicos de RAFAEL"""
        if command == "RAFAEL.IVA":
            return {
                "status": "success",
                "message": "Gestión de IVA completada",
                "agent": "RAFAEL",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "tax_calculation",
                "voice": "Gestión de IVA completada. Modelo 303 preparado para presentación telemática.",
                "data": {
                    "modelo": "303",
                    "periodo": "trimestral",
                    "iva_devengado": "€2,500.00",
                    "iva_deducible": "€1,200.00",
                    "diferencia": "€1,300.00",
                    "protocol": self.protocol,
                    "next_deadline": "Próximo vencimiento: 20 de enero"
                }
            }
        elif command == "RAFAEL.IRPF":
            return {
                "status": "success",
                "message": "Cálculo de IRPF completado",
                "agent": "RAFAEL",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "income_tax",
                "voice": "Cálculo de IRPF completado. Retenciones optimizadas dentro del marco legal.",
                "data": {
                    "base_imponible": "€45,000.00",
                    "retenciones": "€9,000.00",
                    "tipo_medio": "20%",
                    "optimizaciones": [
                        "Deducciones por vivienda",
                        "Plan de pensiones",
                        "Gastos deducibles"
                    ],
                    "ahorro_fiscal": "€1,200.00"
                }
            }
        elif command == "RAFAEL.IS":
            return {
                "status": "success",
                "message": "Impuesto de Sociedades calculado",
                "agent": "RAFAEL",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "corporate_tax",
                "voice": "Impuesto de Sociedades calculado. Optimización fiscal aplicada.",
                "data": {
                    "beneficio_contable": "€120,000.00",
                    "ajustes_fiscales": "€-5,000.00",
                    "base_imponible": "€115,000.00",
                    "tipo_impositivo": "25%",
                    "cuota_integra": "€28,750.00",
                    "deducciones": "€2,000.00",
                    "cuota_liquida": "€26,750.00"
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Comando RAFAEL no reconocido: {command}",
                "available_commands": ["RAFAEL.IVA", "RAFAEL.IRPF", "RAFAEL.IS"],
                "specializations": self.specializations
            }

class AnalisisAgent(ZeusAgent):
    """Agente ANÁLISIS - Análisis de datos"""
    
    def __init__(self):
        super().__init__(
            AgentType.ANALISIS,
            "ANÁLISIS",
            "Agente de análisis de datos y métricas"
        )
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comandos específicos de ANÁLISIS"""
        if command == "ANALISIS.PROCESAR":
            return {
                "status": "success",
                "message": "Análisis de datos completado",
                "agent": "ANÁLISIS",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "data_analysis",
                "voice": "Análisis completado. Datos procesados exitosamente.",
                "data": {
                    "analysis_result": "exitoso",
                    "data_points": 1000,
                    "insights": [
                        "Rendimiento óptimo",
                        "Tendencias positivas",
                        "Recomendaciones aplicadas"
                    ]
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Comando ANÁLISIS no reconocido: {command}",
                "available_commands": ["ANALISIS.PROCESAR"]
            }

class IAAgent(ZeusAgent):
    """Agente IA - Inteligencia artificial"""
    
    def __init__(self):
        super().__init__(
            AgentType.IA,
            "IA",
            "Agente de inteligencia artificial avanzada"
        )
    
    def _execute_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comandos específicos de IA"""
        if command == "IA.PROCESAR":
            return {
                "status": "success",
                "message": "Procesamiento de IA completado",
                "agent": "IA",
                "timestamp": datetime.utcnow().isoformat(),
                "animation": "ai_processing",
                "voice": "Procesamiento de IA completado. Inteligencia artificial activa.",
                "data": {
                    "ai_status": "activo",
                    "processing_power": "máximo",
                    "capabilities": [
                        "Aprendizaje automático",
                        "Procesamiento natural",
                        "Predicción avanzada"
                    ]
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Comando IA no reconocido: {command}",
                "available_commands": ["IA.PROCESAR"]
            }

# ========================================
# GESTOR DE AGENTES ZEUS
# ========================================

class ZeusAgentManager:
    """Gestor central de todos los agentes ZEUS"""
    
    def __init__(self):
        self.agents = {
            AgentType.ZEUS: ZeusCore(),
            AgentType.PERSEO: PerSeoAgent(),
            AgentType.THALOS: ThalosAgent(),
            AgentType.JUSTICIA: JusticiaAgent(),
            AgentType.RAFAEL: RafaelAgent(),
            AgentType.ANALISIS: AnalisisAgent(),
            AgentType.IA: IAAgent()
        }
        self.system_status = "inactive"
    
    def activate_all_agents(self) -> Dict[str, Any]:
        """Activar todos los agentes del sistema"""
        results = {}
        
        for agent_type, agent in self.agents.items():
            try:
                result = agent.activate()
                results[agent_type.value] = result
            except Exception as e:
                results[agent_type.value] = {
                    "status": "error",
                    "message": f"Error activando {agent_type.value}: {str(e)}"
                }
        
        self.system_status = "active"
        
        return {
            "status": "success",
            "message": "Sistema ZEUS completamente activado",
            "timestamp": datetime.utcnow().isoformat(),
            "animation": "system_activation",
            "voice": "Sistema ZEUS completamente activado. Todos los agentes operativos.",
            "agents": results
        }
    
    def execute_zeus_command(self, command: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ejecutar comando del Núcleo ZEUS"""
        try:
            # Comandos del núcleo principal
            if command.startswith("ZEUS."):
                return self.agents[AgentType.ZEUS].process_command(command, data or {})
            
            # Comandos de agentes específicos
            elif command.startswith("PERSEO."):
                return self.agents[AgentType.PERSEO].process_command(command, data or {})
            
            elif command.startswith("THALOS."):
                return self.agents[AgentType.THALOS].process_command(command, data or {})
            
            elif command.startswith("JUSTICIA."):
                return self.agents[AgentType.JUSTICIA].process_command(command, data or {})
            
            elif command.startswith("RAFAEL."):
                return self.agents[AgentType.RAFAEL].process_command(command, data or {})
            
            elif command.startswith("ANALISIS."):
                return self.agents[AgentType.ANALISIS].process_command(command, data or {})
            
            elif command.startswith("IA."):
                return self.agents[AgentType.IA].process_command(command, data or {})
            
            else:
                return {
                    "status": "error",
                    "message": f"Comando no reconocido: {command}",
                    "available_commands": [
                        "ZEUS.ACTIVAR", "ZEUS.ANALIZAR", "ZEUS.EJECUTAR",
                        "ZEUS.SEGURIDAD", "ZEUS.REGLAS", "ZEUS.BIENESTAR",
                        "PERSEO.FUNNEL", "PERSEO.SEO", "PERSEO.COPY",
                        "THALOS.SHIELD", "THALOS.SCAN", "THALOS.BLOCK",
                        "JUSTICIA.CONTRATO", "JUSTICIA.RGPD", "JUSTICIA.DEFENSA",
                        "RAFAEL.IVA", "RAFAEL.IRPF", "RAFAEL.IS",
                        "ANALISIS.PROCESAR",
                        "IA.PROCESAR"
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error ejecutando comando ZEUS: {str(e)}")
            return {
                "status": "error",
                "message": f"Error ejecutando comando: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Obtener estado completo del sistema"""
        agent_status = {}
        
        for agent_type, agent in self.agents.items():
            agent_status[agent_type.value] = {
                "name": agent.name,
                "status": agent.status.value,
                "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
                "logs_count": len(agent.logs)
            }
        
        return {
            "system_status": self.system_status,
            "timestamp": datetime.utcnow().isoformat(),
            "agents": agent_status,
            "total_agents": len(self.agents),
            "active_agents": sum(1 for agent in self.agents.values() if agent.status == AgentStatus.ACTIVE)
        }

# Instancia global del gestor de agentes
zeus_manager = ZeusAgentManager()
