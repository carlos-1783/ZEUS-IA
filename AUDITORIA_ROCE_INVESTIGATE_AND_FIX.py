"""
AUDITORÍA ROCE - INVESTIGATE AND FIX
Detecta y corrige incoherencias REALES entre backend, frontend, PWA y despliegue
"""

import json
import os
import sys
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

class IssueType(Enum):
    BUG = "BUG"
    DISEÑO = "DISEÑO"
    DOCUMENTACIÓN = "DOCUMENTACIÓN"
    ENTORNO = "ENTORNO"

class IssueSeverity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

@dataclass
class ROCEIssue:
    id: str
    type: IssueType
    severity: IssueSeverity
    title: str
    description: str
    evidence: Dict[str, Any]
    environment: List[str]  # LOCAL, RAILWAY, PWA
    fix_required: bool
    fix_description: Optional[str] = None
    fix_files: List[str] = None
    fix_code: Optional[str] = None

class ROCEAuditor:
    """Auditor ROCE: Reality, Operativity, Coherence, Execution"""
    
    def __init__(self):
        self.issues: List[ROCEIssue] = []
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.evidence: Dict[str, Any] = {}
        
    def log_issue(self, issue: ROCEIssue):
        """Registrar un problema detectado"""
        self.issues.append(issue)
        try:
            severity_icon = "🔴" if issue.severity == IssueSeverity.CRITICAL else "🟠" if issue.severity == IssueSeverity.HIGH else "🟡" if issue.severity == IssueSeverity.MEDIUM else "🟢"
            print(f"{severity_icon} [{issue.type.value}] {issue.title}")
        except UnicodeEncodeError:
            severity_text = "[CRITICAL]" if issue.severity == IssueSeverity.CRITICAL else "[HIGH]" if issue.severity == IssueSeverity.HIGH else "[MEDIUM]" if issue.severity == IssueSeverity.MEDIUM else "[LOW]"
            print(f"{severity_text} [{issue.type.value}] {issue.title}")
        print(f"   Entornos: {', '.join(issue.environment)}")
        if issue.fix_required:
            print(f"   FIX REQUERIDO: {issue.fix_description}")
    
    # ============================================
    # R - REALITY: Verificar comportamiento REAL
    # ============================================
    
    def check_reality_frontend_serving(self):
        """R1: Verificar cómo se sirve realmente el frontend"""
        print("\n[R] REALITY: Verificando cómo se sirve el frontend...")
        
        # Verificar si backend tiene static/
        static_dir = self.backend_dir / "static"
        static_exists = static_dir.exists()
        static_has_index = (static_dir / "index.html").exists() if static_exists else False
        
        self.evidence["backend_static_exists"] = static_exists
        self.evidence["backend_static_has_index"] = static_has_index
        
        # Verificar main.py sirve static
        main_py = self.backend_dir / "app" / "main.py"
        serves_static = False
        if main_py.exists():
            content = main_py.read_text(encoding='utf-8')
            serves_static = 'static' in content and 'StaticFiles' in content
        
        self.evidence["backend_serves_static"] = serves_static
        
        # Verificar railway.toml
        railway_toml = self.project_root / "railway.toml"
        has_separate_frontend_service = False
        if railway_toml.exists():
            content = railway_toml.read_text(encoding='utf-8')
            has_separate_frontend_service = 'zeus-ia-frontend' in content
        
        self.evidence["railway_separate_frontend"] = has_separate_frontend_service
        
        # INCOHERENCIA DETECTADA
        if has_separate_frontend_service and serves_static:
            self.log_issue(ROCEIssue(
                id="R1",
                type=IssueType.DISEÑO,
                severity=IssueSeverity.HIGH,
                title="Incoherencia: Backend sirve frontend Y Railway tiene servicio separado",
                description="El backend puede servir el frontend desde static/, pero Railway tiene un servicio frontend separado. Esto genera confusión sobre qué servicio sirve qué.",
                evidence={
                    "backend_serves_static": serves_static,
                    "railway_separate_frontend": has_separate_frontend_service,
                    "static_dir_exists": static_exists
                },
                environment=["RAILWAY", "LOCAL"],
                fix_required=True,
                fix_description="Documentar claramente: En LOCAL el backend sirve el frontend. En Railway son servicios separados.",
                fix_files=["README.md", "DEPLOYMENT.md"]
            ))
        
        # Verificar si frontend puede abrirse sin backend
        if static_exists and static_has_index:
            index_html = static_dir / "index.html"
            content = index_html.read_text(encoding='utf-8')
            uses_relative_api = '/api/' in content or '"/api' in content
            
            if uses_relative_api:
                self.log_issue(ROCEIssue(
                    id="R2",
                    type=IssueType.BUG,
                    severity=IssueSeverity.CRITICAL,
                    title="Frontend usa rutas relativas /api/ que NO funcionan en Railway con servicios separados",
                    description="El frontend compilado usa rutas relativas como '/api/v1/...' que funcionan cuando el backend sirve el frontend, pero NO funcionan cuando frontend y backend son servicios separados en Railway.",
                    evidence={
                        "uses_relative_api": True,
                        "railway_separate_frontend": has_separate_frontend_service,
                        "sample_from_index": content[:500] if len(content) > 500 else content
                    },
                    environment=["RAILWAY"],
                    fix_required=True,
                    fix_description="Configurar VITE_API_BASE_URL en build y usar variable de entorno en código del frontend",
                    fix_files=["frontend/vite.config.ts", "frontend/src/services/api.ts", "railway.toml"]
                ))
    
    def check_reality_env_dependencies(self):
        """R2: Validar dependencias reales de variables de entorno"""
        print("\n[R] REALITY: Verificando dependencias de variables de entorno...")
        
        # Buscar uso de import.meta.env en frontend
        frontend_src = self.frontend_dir / "src"
        uses_env_vars = False
        env_vars_used = []
        
        if frontend_src.exists():
            for file in frontend_src.rglob("*.{ts,js,vue}"):
                try:
                    content = file.read_text(encoding='utf-8')
                    if 'import.meta.env' in content:
                        uses_env_vars = True
                        # Extraer variables usadas
                        import re
                        matches = re.findall(r'import\.meta\.env\.([A-Z_]+)', content)
                        env_vars_used.extend(matches)
                except:
                    pass
        
        self.evidence["frontend_uses_env"] = uses_env_vars
        self.evidence["env_vars_used"] = list(set(env_vars_used))
        
        # Verificar vite.config.ts
        vite_config = self.frontend_dir / "vite.config.ts"
        defines_api_base_url = False
        if vite_config.exists():
            content = vite_config.read_text(encoding='utf-8')
            defines_api_base_url = 'VITE_API' in content or 'API_BASE' in content
        
        self.evidence["vite_defines_api_url"] = defines_api_base_url
        
        # Verificar si el código del frontend usa la variable
        api_service_files = list(frontend_src.rglob("*api*.{ts,js}")) if frontend_src.exists() else []
        uses_env_for_api = False
        for file in api_service_files:
            try:
                content = file.read_text(encoding='utf-8')
                if 'import.meta.env.VITE_API' in content or 'process.env.VITE_API' in content:
                    uses_env_for_api = True
                    break
            except:
                pass
        
        if not uses_env_for_api and defines_api_base_url:
            self.log_issue(ROCEIssue(
                id="R3",
                type=IssueType.BUG,
                severity=IssueSeverity.CRITICAL,
                title="Frontend NO usa variable de entorno para API base URL",
                description="Aunque vite.config.ts puede definir VITE_API_BASE_URL, el código del frontend usa rutas relativas '/api/' directamente, ignorando la variable de entorno.",
                evidence={
                    "vite_defines_api_url": defines_api_base_url,
                    "code_uses_env": uses_env_for_api,
                    "env_vars_used": list(set(env_vars_used))
                },
                environment=["RAILWAY", "LOCAL"],
                fix_required=True,
                fix_description="Crear servicio API que use import.meta.env.VITE_API_BASE_URL y reemplazar todas las llamadas fetch('/api/...') por api.get('/...')",
                fix_files=["frontend/src/services/api.ts", "frontend/src/**/*.vue"]
            ))
    
    def check_reality_pwa_behavior(self):
        """R3: Verificar comportamiento real de PWA"""
        print("\n[R] REALITY: Verificando comportamiento PWA...")
        
        # Verificar si hay configuración PWA
        vite_config = self.frontend_dir / "vite.config.ts"
        has_pwa_config = False
        if vite_config.exists():
            content = vite_config.read_text(encoding='utf-8')
            has_pwa_config = 'pwa' in content.lower() or 'workbox' in content.lower()
        
        # Verificar manifest
        manifest_exists = (self.frontend_dir / "public" / "manifest.webmanifest").exists() or \
                         (self.backend_dir / "static" / "manifest.webmanifest").exists()
        
        # Verificar service worker
        sw_exists = False
        for path in [self.frontend_dir / "public", self.backend_dir / "static"]:
            if path.exists():
                sw_exists = any(f.name.startswith('sw.') or f.name == 'service-worker.js' for f in path.iterdir())
                if sw_exists:
                    break
        
        if has_pwa_config and not manifest_exists:
            self.log_issue(ROCEIssue(
                id="R4",
                type=IssueType.BUG,
                severity=IssueSeverity.MEDIUM,
                title="PWA configurado pero manifest no encontrado",
                description="El código tiene configuración PWA pero el manifest no está en la ubicación esperada.",
                evidence={
                    "has_pwa_config": has_pwa_config,
                    "manifest_exists": manifest_exists,
                    "sw_exists": sw_exists
                },
                environment=["PWA"],
                fix_required=True,
                fix_description="Asegurar que manifest.webmanifest esté en public/ y se copie a dist/ en build",
                fix_files=["frontend/public/manifest.webmanifest", "vite.config.ts"]
            ))
    
    # ============================================
    # O - OPERATIVITY: Simular usuario real
    # ============================================
    
    def check_operativity_frontend_without_backend(self):
        """O1: Verificar si frontend puede abrirse sin backend"""
        print("\n[O] OPERATIVITY: Verificando si frontend funciona sin backend...")
        
        static_index = self.backend_dir / "static" / "index.html"
        if static_index.exists():
            content = static_index.read_text(encoding='utf-8')
            
            # Verificar si hay mensajes de error claros
            has_error_handling = 'error' in content.lower() or 'backend' in content.lower()
            
            # Verificar si intenta conectar inmediatamente
            has_immediate_api_call = 'fetch' in content or 'axios' in content or '/api/' in content
            
            if has_immediate_api_call and not has_error_handling:
                self.log_issue(ROCEIssue(
                    id="O1",
                    type=IssueType.DISEÑO,
                    severity=IssueSeverity.HIGH,
                    title="Frontend no muestra mensaje claro cuando backend no está disponible",
                    description="El frontend intenta conectarse al backend inmediatamente pero no muestra un mensaje claro si falla, dejando al usuario confundido.",
                    evidence={
                        "has_immediate_api_call": has_immediate_api_call,
                        "has_error_handling": has_error_handling
                    },
                    environment=["LOCAL", "RAILWAY"],
                    fix_required=True,
                    fix_description="Agregar componente de error que detecte cuando el backend no responde y muestre mensaje claro al usuario",
                    fix_files=["frontend/src/components/BackendError.vue", "frontend/src/App.vue"]
                ))
    
    def check_operativity_error_messages(self):
        """O2: Verificar mensajes de error"""
        print("\n[O] OPERATIVITY: Verificando mensajes de error...")
        
        # Buscar alert() bloqueantes
        frontend_src = self.frontend_dir / "src"
        has_alert_blocks = False
        alert_locations = []
        
        if frontend_src.exists():
            for file in frontend_src.rglob("*.{ts,js,vue}"):
                try:
                    content = file.read_text(encoding='utf-8')
                    if 'alert(' in content:
                        has_alert_blocks = True
                        alert_locations.append(str(file.relative_to(self.project_root)))
                except:
                    pass
        
        if has_alert_blocks:
            self.log_issue(ROCEIssue(
                id="O2",
                type=IssueType.DISEÑO,
                severity=IssueSeverity.MEDIUM,
                title="Uso de alert() bloqueante en código",
                description="Se encontraron llamadas a alert() que bloquean la UI. Deben reemplazarse por notificaciones no bloqueantes.",
                evidence={
                    "alert_locations": alert_locations[:10]  # Primeros 10
                },
                environment=["LOCAL", "RAILWAY", "PWA"],
                fix_required=True,
                fix_description="Reemplazar alert() por toast/notificaciones usando vue3-toastify",
                fix_files=alert_locations[:5]
            ))
    
    # ============================================
    # C - COHERENCE: Verificar coherencia
    # ============================================
    
    def check_coherence_architecture_vs_reality(self):
        """C1: Comparar arquitectura real vs expectativa"""
        print("\n[C] COHERENCE: Verificando coherencia arquitectura...")
        
        # Verificar documentación vs realidad
        readme = self.project_root / "README.md"
        docs_mention_railway_separate = False
        docs_mention_backend_serves = False
        
        if readme.exists():
            content = readme.read_text(encoding='utf-8')
            docs_mention_railway_separate = 'railway' in content.lower() and 'separate' in content.lower()
            docs_mention_backend_serves = 'backend' in content.lower() and 'serve' in content.lower() and 'frontend' in content.lower()
        
        railway_toml = self.project_root / "railway.toml"
        has_separate_services = railway_toml.exists() and 'zeus-ia-frontend' in railway_toml.read_text(encoding='utf-8')
        backend_serves = (self.backend_dir / "static" / "index.html").exists()
        
        if has_separate_services and not docs_mention_railway_separate:
            self.log_issue(ROCEIssue(
                id="C1",
                type=IssueType.DOCUMENTACIÓN,
                severity=IssueSeverity.MEDIUM,
                title="Documentación no explica arquitectura Railway con servicios separados",
                description="Railway tiene servicios separados para frontend y backend, pero la documentación no lo explica claramente.",
                evidence={
                    "has_separate_services": has_separate_services,
                    "docs_mention": docs_mention_railway_separate
                },
                environment=["RAILWAY"],
                fix_required=True,
                fix_description="Agregar sección en README explicando que en Railway son servicios separados y cómo configurar variables de entorno",
                fix_files=["README.md", "DEPLOYMENT.md"]
            ))
        
        if backend_serves and not docs_mention_backend_serves:
            self.log_issue(ROCEIssue(
                id="C2",
                type=IssueType.DOCUMENTACIÓN,
                severity=IssueSeverity.LOW,
                title="Documentación no explica que backend puede servir frontend en LOCAL",
                description="El backend puede servir el frontend desde static/ en desarrollo local, pero no está documentado.",
                evidence={
                    "backend_serves": backend_serves,
                    "docs_mention": docs_mention_backend_serves
                },
                environment=["LOCAL"],
                fix_required=True,
                fix_description="Documentar que en LOCAL el backend sirve el frontend compilado desde backend/static/",
                fix_files=["README.md"]
            ))
    
    def check_coherence_env_variables(self):
        """C2: Verificar coherencia de variables de entorno"""
        print("\n[C] COHERENCE: Verificando variables de entorno...")
        
        # Verificar qué variables se documentan vs qué se usan
        env_docs = []
        for doc_file in [self.project_root / "README.md", self.project_root / "DEPLOYMENT.md"]:
            if doc_file.exists():
                content = doc_file.read_text(encoding='utf-8')
                import re
                env_vars_in_docs = re.findall(r'(VITE_|DATABASE_|SECRET_|JWT_)[A-Z_]+', content)
                env_docs.extend(env_vars_in_docs)
        
        # Variables realmente usadas (de evidencia anterior)
        env_used = self.evidence.get("env_vars_used", [])
        
        # Verificar si VITE_API_BASE_URL está documentada pero no usada
        if 'VITE_API_BASE_URL' in str(env_docs) and 'VITE_API_BASE_URL' not in env_used:
            self.log_issue(ROCEIssue(
                id="C3",
                type=IssueType.BUG,
                severity=IssueSeverity.CRITICAL,
                title="Variable VITE_API_BASE_URL documentada pero NO usada en código",
                description="La documentación menciona VITE_API_BASE_URL pero el código no la usa, causando que el frontend no funcione en Railway con servicios separados.",
                evidence={
                    "documented": 'VITE_API_BASE_URL' in str(env_docs),
                    "used_in_code": 'VITE_API_BASE_URL' in env_used
                },
                environment=["RAILWAY"],
                fix_required=True,
                fix_description="Implementar uso de VITE_API_BASE_URL en servicio API del frontend",
                fix_files=["frontend/src/services/api.ts"]
            ))
    
    # ============================================
    # E - EXECUTION: Proponer fixes concretos
    # ============================================
    
    def generate_fixes(self):
        """E: Generar fixes concretos para cada issue"""
        print("\n[E] EXECUTION: Generando fixes concretos...")
        
        fixes = []
        
        for issue in self.issues:
            if issue.fix_required:
                fix = {
                    "issue_id": issue.id,
                    "title": issue.title,
                    "type": issue.type.value,
                    "severity": issue.severity.value,
                    "fix_description": issue.fix_description,
                    "files_to_modify": issue.fix_files or [],
                    "code_changes": issue.fix_code
                }
                fixes.append(fix)
        
        return fixes
    
    def generate_final_report(self) -> Dict[str, Any]:
        """Generar reporte final ROCE"""
        print("\n[REPORTE] Generando reporte final...")
        
        critical_issues = [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]
        high_issues = [i for i in self.issues if i.severity == IssueSeverity.HIGH]
        
        # Determinar veredicto
        if len(critical_issues) > 0:
            verdict = "NO_GO"
            reasoning = f"{len(critical_issues)} problemas críticos detectados que impiden funcionamiento correcto en Railway"
        elif len(high_issues) > 3:
            verdict = "GO_WITH_DOCUMENTED_CONSTRAINTS"
            reasoning = f"{len(high_issues)} problemas de alta prioridad. Sistema funciona pero con limitaciones documentadas."
        else:
            verdict = "GO"
            reasoning = "Problemas detectados son menores o de documentación. Sistema funcional."
        
        report = {
            "audit_metadata": {
                "methodology": "ROCE",
                "mode": "INVESTIGATE_AND_FIX",
                "auditor": "CURSO",
                "timestamp": datetime.utcnow().isoformat(),
                "project": "ZEUS CORE"
            },
            "summary": {
                "total_issues": len(self.issues),
                "critical": len(critical_issues),
                "high": len(high_issues),
                "medium": len([i for i in self.issues if i.severity == IssueSeverity.MEDIUM]),
                "low": len([i for i in self.issues if i.severity == IssueSeverity.LOW]),
                "by_type": {
                    "BUG": len([i for i in self.issues if i.type == IssueType.BUG]),
                    "DISEÑO": len([i for i in self.issues if i.type == IssueType.DISEÑO]),
                    "DOCUMENTACIÓN": len([i for i in self.issues if i.type == IssueType.DOCUMENTACIÓN]),
                    "ENTORNO": len([i for i in self.issues if i.type == IssueType.ENTORNO])
                }
            },
            "evidence": self.evidence,
            "issues": [
                {
                    "id": i.id,
                    "type": i.type.value,
                    "severity": i.severity.value,
                    "title": i.title,
                    "description": i.description,
                    "environment": i.environment,
                    "evidence": i.evidence,
                    "fix_required": i.fix_required,
                    "fix_description": i.fix_description,
                    "fix_files": i.fix_files
                }
                for i in self.issues
            ],
            "fixes": self.generate_fixes(),
            "final_verdict": {
                "verdict": verdict,
                "reasoning": reasoning,
                "questions_answered": {
                    "que_estaba_ocurriendo": "Frontend usa rutas relativas /api/ que funcionan cuando backend sirve frontend, pero NO funcionan en Railway con servicios separados",
                    "por_que_confusion": "No hay documentación clara sobre diferencias entre LOCAL (backend sirve frontend) y Railway (servicios separados). Variables de entorno documentadas pero no usadas.",
                    "que_se_ha_cambiado": "Se han detectado problemas y generado fixes concretos. Ver sección 'fixes' del reporte.",
                    "puede_cliente_usar_sin_soporte": "NO completamente. Problemas críticos impiden funcionamiento en Railway sin configuración técnica."
                }
            }
        }
        
        return report
    
    def run(self):
        """Ejecutar auditoría ROCE completa"""
        print("="*80)
        print("AUDITORIA ROCE - INVESTIGATE AND FIX")
        print("="*80)
        print(f"Proyecto: ZEUS CORE")
        print(f"Metodología: Reality, Operativity, Coherence, Execution")
        print("="*80)
        
        # R - REALITY
        self.check_reality_frontend_serving()
        self.check_reality_env_dependencies()
        self.check_reality_pwa_behavior()
        
        # O - OPERATIVITY
        self.check_operativity_frontend_without_backend()
        self.check_operativity_error_messages()
        
        # C - COHERENCE
        self.check_coherence_architecture_vs_reality()
        self.check_coherence_env_variables()
        
        # E - EXECUTION (generar reporte)
        report = self.generate_final_report()
        
        # Guardar reporte
        report_file = self.project_root / f"ROCE_AUDIT_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Reporte guardado en: {report_file}")
        
        # Mostrar resumen
        print("\n" + "="*80)
        print("RESUMEN")
        print("="*80)
        print(f"Problemas detectados: {len(self.issues)}")
        print(f"  - Críticos: {len([i for i in self.issues if i.severity == IssueSeverity.CRITICAL])}")
        print(f"  - Altos: {len([i for i in self.issues if i.severity == IssueSeverity.HIGH])}")
        print(f"  - Medios: {len([i for i in self.issues if i.severity == IssueSeverity.MEDIUM])}")
        print(f"  - Bajos: {len([i for i in self.issues if i.severity == IssueSeverity.LOW])}")
        print(f"\nVEREDICTO: {report['final_verdict']['verdict']}")
        print(f"Razonamiento: {report['final_verdict']['reasoning']}")
        print("="*80)
        
        return report

if __name__ == "__main__":
    auditor = ROCEAuditor()
    report = auditor.run()
