"""
🎯 Script para generar actividades de demostración
Crea actividades de ejemplo para mostrar cómo trabajan los agentes
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.activity_logger import activity_logger
from datetime import datetime, timedelta
import random

def generate_perseo_activities():
    """Generar actividades de PERSEO (Marketing)"""
    print("\n🎨 Generando actividades de PERSEO...")
    
    activities = [
        {
            "action_type": "campaign_created",
            "description": "Campaña creada en Google Ads: 'Marketing Digital España'",
            "details": {
                "platform": "Google Ads",
                "campaign_name": "Marketing Digital España",
                "target_audience": "Empresas B2B",
                "keywords": ["marketing digital", "automatización", "IA"]
            },
            "metrics": {
                "budget": 500,
                "roi": 4.2,
                "clicks": 1200,
                "conversions": 45
            }
        },
        {
            "action_type": "campaign_optimized",
            "description": "Optimización de keywords: +15% CTR",
            "details": {
                "campaign": "Marketing Digital España",
                "optimization_type": "keywords",
                "changes": "Pausadas 12 keywords de bajo rendimiento"
            },
            "metrics": {
                "improvement": 15,
                "ctr_before": 2.1,
                "ctr_after": 2.4
            }
        },
        {
            "action_type": "campaign_created",
            "description": "Campaña Meta Ads creada: 'Instagram Awareness'",
            "details": {
                "platform": "Meta Ads",
                "campaign_name": "Instagram Awareness",
                "objective": "Brand Awareness"
            },
            "metrics": {
                "budget": 300,
                "reach": 50000,
                "engagement_rate": 3.8
            }
        },
        {
            "action_type": "content_created",
            "description": "Post de LinkedIn publicado: 'IA en el Marketing'",
            "details": {
                "platform": "LinkedIn",
                "topic": "Inteligencia Artificial",
                "content_type": "Artículo educativo"
            },
            "metrics": {
                "views": 2500,
                "likes": 145,
                "comments": 23,
                "shares": 67
            }
        }
    ]
    
    for activity in activities:
        activity_logger.log_activity(
            agent_name="PERSEO",
            action_type=activity["action_type"],
            action_description=activity["description"],
            details=activity["details"],
            metrics=activity["metrics"],
            status="completed",
            priority="normal"
        )
    
    print(f"✅ {len(activities)} actividades de PERSEO creadas")

def generate_rafael_activities():
    """Generar actividades de RAFAEL (Fiscal)"""
    print("\n📊 Generando actividades de RAFAEL...")
    
    activities = [
        {
            "action_type": "invoice_sent",
            "description": "Factura #2024-045 enviada a Cliente SL",
            "details": {
                "invoice_number": "2024-045",
                "client": "Cliente SL",
                "date": "2024-11-03"
            },
            "metrics": {
                "amount": 1200.00,
                "tax": 252.00,
                "total": 1452.00
            }
        },
        {
            "action_type": "modelo_303_filed",
            "description": "Modelo 303 (IVA Q3) presentado a Hacienda",
            "details": {
                "quarter": 3,
                "year": 2024,
                "status": "Presentado correctamente"
            },
            "metrics": {
                "iva_repercutido": 5600.00,
                "iva_soportado": 2100.00,
                "resultado": 3500.00
            }
        },
        {
            "action_type": "expense_recorded",
            "description": "Gasto registrado: Hosting Railway (Octubre)",
            "details": {
                "category": "Servicios tecnológicos",
                "vendor": "Railway",
                "period": "Octubre 2024"
            },
            "metrics": {
                "amount": 150.00,
                "iva_deducible": 31.50
            }
        }
    ]
    
    for activity in activities:
        activity_logger.log_activity(
            agent_name="RAFAEL",
            action_type=activity["action_type"],
            action_description=activity["description"],
            details=activity["details"],
            metrics=activity["metrics"],
            status="completed",
            priority="normal"
        )
    
    print(f"✅ {len(activities)} actividades de RAFAEL creadas")

def generate_thalos_activities():
    """Generar actividades de THALOS (Seguridad)"""
    print("\n🛡️ Generando actividades de THALOS...")
    
    activities = [
        {
            "action_type": "security_scan",
            "description": "Escaneo de seguridad completado: 0 amenazas",
            "details": {
                "scan_type": "Full system scan",
                "duration": "15 minutos",
                "files_scanned": 45023
            },
            "metrics": {
                "threats_found": 0,
                "vulnerabilities": 0,
                "warnings": 2
            }
        },
        {
            "action_type": "backup_created",
            "description": "Backup automático de base de datos creado",
            "details": {
                "backup_type": "Full database",
                "location": "Railway Storage",
                "encrypted": True
            },
            "metrics": {
                "size_mb": 234,
                "duration_seconds": 45
            }
        },
        {
            "action_type": "threat_blocked",
            "description": "Intento de acceso no autorizado bloqueado",
            "details": {
                "ip_address": "185.234.219.XXX",
                "attack_type": "SQL Injection attempt",
                "endpoint": "/api/v1/users"
            },
            "metrics": {
                "severity": "high",
                "attempts": 15,
                "blocked": True
            }
        }
    ]
    
    for activity in activities:
        activity_logger.log_activity(
            agent_name="THALOS",
            action_type=activity["action_type"],
            action_description=activity["description"],
            details=activity["details"],
            metrics=activity["metrics"],
            status="completed",
            priority="high" if "threat" in activity["action_type"] else "normal"
        )
    
    print(f"✅ {len(activities)} actividades de THALOS creadas")

def generate_justicia_activities():
    """Generar actividades de JUSTICIA (Legal)"""
    print("\n⚖️ Generando actividades de JUSTICIA...")
    
    activities = [
        {
            "action_type": "document_reviewed",
            "description": "Contrato de suscripción revisado y aprobado",
            "details": {
                "document_type": "Subscription Contract",
                "client": "Empresa Test SL",
                "clauses_reviewed": 23
            },
            "metrics": {
                "issues_found": 0,
                "recommendations": 2
            }
        },
        {
            "action_type": "compliance_check",
            "description": "Auditoría GDPR: Sistema cumple con normativa",
            "details": {
                "regulation": "GDPR",
                "areas_checked": ["Consentimiento", "Datos personales", "Derechos ARCO"],
                "status": "Conforme"
            },
            "metrics": {
                "compliance_score": 98,
                "improvements_suggested": 1
            }
        },
        {
            "action_type": "policy_updated",
            "description": "Política de privacidad actualizada",
            "details": {
                "document": "Privacy Policy",
                "changes": "Añadida sección sobre IA generativa",
                "version": "2.1"
            },
            "metrics": {
                "sections_updated": 3
            }
        }
    ]
    
    for activity in activities:
        activity_logger.log_activity(
            agent_name="JUSTICIA",
            action_type=activity["action_type"],
            action_description=activity["description"],
            details=activity["details"],
            metrics=activity["metrics"],
            status="completed",
            priority="normal"
        )
    
    print(f"✅ {len(activities)} actividades de JUSTICIA creadas")

def generate_zeus_activities():
    """Generar actividades de ZEUS CORE (Orquestador)"""
    print("\n⚡ Generando actividades de ZEUS CORE...")
    
    activities = [
        {
            "action_type": "task_delegated",
            "description": "Tarea delegada a PERSEO: Crear campaña Q4",
            "details": {
                "delegated_to": "PERSEO",
                "task": "Crear campaña de marketing Q4",
                "priority": "high"
            },
            "metrics": {
                "response_time": "5s",
                "estimated_completion": "2h"
            }
        },
        {
            "action_type": "coordination",
            "description": "Coordinación: RAFAEL + JUSTICIA para nuevo contrato",
            "details": {
                "agents": ["RAFAEL", "JUSTICIA"],
                "objective": "Revisar términos fiscales de contrato",
                "status": "Completado"
            },
            "metrics": {
                "efficiency": 95,
                "time_saved": "3h"
            }
        },
        {
            "action_type": "whatsapp_response",
            "description": "Respondido consulta de cliente vía WhatsApp",
            "details": {
                "from": "+34612345678",
                "query": "¿Cuánto cuesta ZEUS?",
                "response": "Explicación de planes y precios"
            },
            "metrics": {
                "response_time": "instant",
                "satisfaction": "high"
            }
        }
    ]
    
    for activity in activities:
        activity_logger.log_activity(
            agent_name="ZEUS",
            action_type=activity["action_type"],
            action_description=activity["description"],
            details=activity["details"],
            metrics=activity["metrics"],
            status="completed",
            priority="high"
        )
    
    print(f"✅ {len(activities)} actividades de ZEUS CORE creadas")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎯 GENERADOR DE ACTIVIDADES DE DEMOSTRACIÓN")
    print("="*60)
    
    generate_zeus_activities()
    generate_perseo_activities()
    generate_rafael_activities()
    generate_thalos_activities()
    generate_justicia_activities()
    
    print("\n" + "="*60)
    print("✅ TODAS LAS ACTIVIDADES GENERADAS CORRECTAMENTE")
    print("="*60)
    print("\n📊 Ahora puedes ver las actividades en:")
    print("   https://zeus-ia-production-16d8.up.railway.app/dashboard")
    print("\n💡 Click en cualquier avatar para ver su panel de actividad\n")

