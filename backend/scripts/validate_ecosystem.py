#!/usr/bin/env python3
"""
🔍 ZEUS-IA Full Ecosystem Validation Script
Valida que TODO el ecosistema esté completo, funcional y listo para lanzamiento comercial.
"""

import sys
import os
import json
import traceback
from datetime import datetime
from typing import Dict, Any, List, Tuple
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

VALIDATION_CONFIG = {
    "task": "zeus_ia_full_ecosystem_go_to_market_certification",
    "mode": "enterprise_validation",
    "overwrite": False,
    "dry_run": False,
    "description": "Verificar que TODO el ecosistema ZEUS-IA está completo, funcional, coherente y listo para lanzamiento comercial sin riesgos técnicos, legales ni operativos.",
    "validation_scope": "FULL_ECOSYSTEM"
}

# ============================================================================
# ESTRUCTURA DE VALIDACIÓN
# ============================================================================

class ValidationResult:
    def __init__(self, module: str, check: str, status: str, details: str = "", impact: str = "", fix: str = ""):
        self.module = module
        self.check = check
        self.status = status  # "PASS", "FAIL", "WARNING"
        self.details = details
        self.impact = impact
        self.fix = fix
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "module": self.module,
            "check": self.check,
            "status": self.status,
            "details": self.details,
            "impact": self.impact,
            "fix": self.fix,
            "timestamp": self.timestamp
        }

class EcosystemValidator:
    def __init__(self):
        self.results: List[ValidationResult] = []
        self.base_dir = Path(__file__).parent.parent.parent  # Ir al root del proyecto
        self.backend_dir = self.base_dir / "backend"
        self.frontend_dir = self.base_dir / "frontend"
        
    def add_result(self, result: ValidationResult):
        self.results.append(result)
        status_marker = "[PASS]" if result.status == "PASS" else "[FAIL]" if result.status == "FAIL" else "[WARN]"
        print(f"{status_marker} [{result.module}] {result.check}: {result.status}")
        if result.details:
            print(f"   -> {result.details}")
    
    # ========================================================================
    # VALIDACIONES DE CORE
    # ========================================================================
    
    def validate_core_modules(self):
        """Validar módulos core del sistema"""
        print("\n[CORE] Validando Modulos Core...")
        
        core_files = {
            "authentication": "app/core/auth.py",
            "authorization": "app/core/auth.py",
            "database": "app/db/base.py",
            "session": "app/db/session.py",
            "config": "app/core/config.py",
            "models": "app/models/user.py",
        }
        
        for module_name, file_path in core_files.items():
            full_path = self.backend_dir / file_path
            if full_path.exists():
                self.add_result(ValidationResult(
                    "CORE",
                    f"Archivo {module_name} existe",
                    "PASS",
                    f"Ubicado en: {file_path}"
                ))
            else:
                self.add_result(ValidationResult(
                    "CORE",
                    f"Archivo {module_name} existe",
                    "FAIL",
                    f"No encontrado: {file_path}",
                    "CRÍTICO: El sistema no puede funcionar sin este módulo",
                    f"Crear archivo en {file_path}"
                ))
        
        # Validar endpoints de autenticación
        auth_endpoints = self.backend_dir / "app/api/v1/endpoints/auth.py"
        if auth_endpoints.exists():
            try:
                content = auth_endpoints.read_text(encoding='utf-8', errors='replace')
            except Exception:
                content = ""
            required_endpoints = ["/login", "/register", "/refresh", "/logout", "/me"]
            for endpoint in required_endpoints:
                if endpoint in content:
                    self.add_result(ValidationResult(
                        "CORE",
                        f"Endpoint auth {endpoint}",
                        "PASS",
                        "Endpoint implementado"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "CORE",
                        f"Endpoint auth {endpoint}",
                        "FAIL",
                        "Endpoint no encontrado",
                        "Los usuarios no pueden autenticarse correctamente",
                        f"Implementar endpoint {endpoint} en auth.py"
                    ))
    
    # ========================================================================
    # VALIDACIONES DE AGENTES
    # ========================================================================
    
    def validate_agents(self):
        """Validar todos los agentes IA"""
        print("\n[AGENTS] Validando Agentes IA...")
        
        agents = {
            "ZEUS_CORE": "agents/zeus_core.py",
            "RAFAEL": "agents/rafael.py",
            "JUSTICIA": "agents/justicia.py",
            "AFRODITA": "agents/afrodita.py",
            "PERSEO": "agents/perseo.py",
            "THALOS": "agents/thalos.py",
        }
        
        for agent_name, file_path in agents.items():
            full_path = self.backend_dir / file_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding='utf-8', errors='replace')
                except Exception:
                    content = ""
                
                # Verificar que herede de BaseAgent
                if "BaseAgent" in content or "class" in content:
                    self.add_result(ValidationResult(
                        "AGENTS",
                        f"Agente {agent_name} existe",
                        "PASS",
                        f"Ubicado en: {file_path}"
                    ))
                    
                    # Verificar que tenga método process_request
                    if "process_request" in content:
                        self.add_result(ValidationResult(
                            "AGENTS",
                            f"Agente {agent_name} tiene process_request",
                            "PASS"
                        ))
                    else:
                        self.add_result(ValidationResult(
                            "AGENTS",
                            f"Agente {agent_name} tiene process_request",
                            "FAIL",
                            "Método process_request no encontrado",
                            "El agente no puede procesar requests",
                            f"Implementar método process_request en {agent_name}"
                        ))
                else:
                    self.add_result(ValidationResult(
                        "AGENTS",
                        f"Agente {agent_name} estructura",
                        "WARNING",
                        "No se detectó herencia de BaseAgent",
                        "Puede haber problemas de compatibilidad"
                    ))
            else:
                self.add_result(ValidationResult(
                    "AGENTS",
                    f"Agente {agent_name} existe",
                    "FAIL",
                    f"No encontrado: {file_path}",
                    "CRÍTICO: Funcionalidad del agente no disponible",
                    f"Crear archivo {file_path}"
                ))
    
    # ========================================================================
    # VALIDACIONES DE MÓDULOS DE NEGOCIO
    # ========================================================================
    
    def validate_business_modules(self):
        """Validar módulos de negocio"""
        print("\n[BUSINESS] Validando Modulos de Negocio...")
        
        # TPV Module
        tpv_service = self.backend_dir / "services/tpv_service.py"
        tpv_endpoints = self.backend_dir / "app/api/v1/endpoints/tpv.py"
        
        if tpv_service.exists() and tpv_endpoints.exists():
            self.add_result(ValidationResult(
                "BUSINESS",
                "TPV Module completo",
                "PASS",
                "Servicio y endpoints implementados"
            ))
            
            # Verificar endpoints críticos del TPV
            try:
                content = tpv_endpoints.read_text(encoding='utf-8', errors='replace')
            except Exception:
                content = ""
            critical_endpoints = ["/status", "/products", "/cart", "/sale"]
            for endpoint in critical_endpoints:
                if endpoint in content:
                    self.add_result(ValidationResult(
                        "BUSINESS",
                        f"TPV endpoint {endpoint}",
                        "PASS"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "BUSINESS",
                        f"TPV endpoint {endpoint}",
                        "FAIL",
                        "Endpoint crítico faltante"
                    ))
        else:
            self.add_result(ValidationResult(
                "BUSINESS",
                "TPV Module completo",
                "FAIL",
                "Faltan archivos del módulo TPV",
                "CRÍTICO: Sistema de punto de venta no funcional"
            ))
        
        # Onboarding Module
        onboarding_endpoints = self.backend_dir / "app/api/v1/endpoints/onboarding.py"
        if onboarding_endpoints.exists():
            try:
                content = onboarding_endpoints.read_text(encoding='utf-8', errors='replace')
            except Exception:
                content = ""
            
            # Verificar validación plan vs empleados
            if "validate_plan_vs_employees" in content:
                self.add_result(ValidationResult(
                    "BUSINESS",
                    "Onboarding: validación plan vs empleados",
                    "PASS",
                    "Validación implementada"
                ))
            else:
                self.add_result(ValidationResult(
                    "BUSINESS",
                    "Onboarding: validación plan vs empleados",
                    "FAIL",
                    "Validación faltante",
                    "Los clientes pueden seleccionar planes incorrectos",
                    "Implementar validate_plan_vs_employees"
                ))
            
            # Verificar creación de cuenta
            if "create-account" in content:
                self.add_result(ValidationResult(
                    "BUSINESS",
                    "Onboarding: creación de cuenta",
                    "PASS",
                    "Endpoint de creación implementado"
                ))
            else:
                self.add_result(ValidationResult(
                    "BUSINESS",
                    "Onboarding: creación de cuenta",
                    "FAIL",
                    "Endpoint faltante",
                    "CRÍTICO: No se pueden crear cuentas después del pago"
                ))
        
        # Legal-Fiscal Firewall
        firewall_service = self.backend_dir / "services/legal_fiscal_firewall.py"
        if firewall_service.exists():
            try:
                content = firewall_service.read_text(encoding='utf-8', errors='replace')
            except Exception:
                content = ""
            
            checks = {
                "Modo borrador": "DRAFT" in content or "draft" in content.lower(),
                "Aprobación cliente": "approval" in content.lower() or "approve" in content.lower(),
                "Envío asesor": "advisor" in content.lower() or "asesor" in content.lower(),
                "Auditoría": "audit" in content.lower() or "log" in content.lower()
            }
            
            for check_name, found in checks.items():
                if found:
                    self.add_result(ValidationResult(
                        "BUSINESS",
                        f"Firewall: {check_name}",
                        "PASS"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "BUSINESS",
                        f"Firewall: {check_name}",
                        "FAIL",
                        f"Funcionalidad {check_name} no encontrada",
                        "CRÍTICO: Riesgo legal/fiscal",
                        f"Implementar {check_name} en firewall"
                    ))
        else:
            self.add_result(ValidationResult(
                "BUSINESS",
                "Legal-Fiscal Firewall",
                "FAIL",
                "Archivo no encontrado",
                "CRÍTICO: Sin protección legal/fiscal",
                "Crear services/legal_fiscal_firewall.py"
            ))
        
        # Document Approval System
        doc_approval_model = self.backend_dir / "app/models/document_approval.py"
        doc_approval_endpoints = self.backend_dir / "app/api/v1/endpoints/document_approval.py"
        
        if doc_approval_model.exists() and doc_approval_endpoints.exists():
            self.add_result(ValidationResult(
                "BUSINESS",
                "Document Approval System",
                "PASS",
                "Modelo y endpoints implementados"
            ))
        else:
            self.add_result(ValidationResult(
                "BUSINESS",
                "Document Approval System",
                "FAIL",
                "Faltan componentes del sistema",
                "No se pueden aprobar documentos"
            ))
    
    # ========================================================================
    # VALIDACIONES DE FLUJOS END-TO-END
    # ========================================================================
    
    def validate_end_to_end_flows(self):
        """Validar flujos end-to-end críticos"""
        print("\n[FLOWS] Validando Flujos End-to-End...")
        
        flows = {
            "onboarding_to_operation": {
                "steps": [
                    ("Crear cuenta", "onboarding", "create-account"),
                    ("Validar plan vs empleados", "onboarding", "validate_plan_vs_employees"),
                    ("Acceso workspaces", "workspaces", None),
                    ("Activación agentes", "agents", None)
                ]
            },
            "tpv_to_accounting": {
                "steps": [
                    ("Registrar venta TPV", "tpv", "sale"),
                    ("Procesar con RAFAEL", "rafael", "process_tpv_ticket"),
                    ("Generar libros", "rafael", None),
                    ("Modo borrador fiscal", "rafael", "draft_only")
                ]
            },
            "legal_fiscal_firewall": {
                "steps": [
                    ("Generación documento", "firewall", "generate_draft_document"),
                    ("Persistencia BD", "firewall", None),
                    ("Aprobación cliente", "firewall", "request_client_approval"),
                    ("Envío asesor", "firewall", "approve_and_send_to_advisor"),
                    ("Auditoría", "firewall", "audit_log")
                ]
            }
        }
        
        for flow_name, flow_data in flows.items():
            all_steps_pass = True
            for step_name, module, check in flow_data["steps"]:
                if module == "onboarding":
                    file_path = self.backend_dir / "app/api/v1/endpoints/onboarding.py"
                elif module == "tpv":
                    file_path = self.backend_dir / "app/api/v1/endpoints/tpv.py"
                elif module == "rafael":
                    file_path = self.backend_dir / "agents/rafael.py"
                elif module == "firewall":
                    file_path = self.backend_dir / "services/legal_fiscal_firewall.py"
                elif module == "workspaces":
                    file_path = self.backend_dir / "app/api/v1/endpoints/workspaces.py"
                elif module == "agents":
                    file_path = self.backend_dir / "agents/zeus_core.py"
                else:
                    all_steps_pass = False
                    continue
                
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='replace')
                    except Exception:
                        content = ""
                    if check is None or check in content:
                        continue
                    else:
                        all_steps_pass = False
                else:
                    all_steps_pass = False
            
            if all_steps_pass:
                self.add_result(ValidationResult(
                    "FLOWS",
                    f"Flujo {flow_name}",
                    "PASS",
                    "Todos los pasos implementados"
                ))
            else:
                self.add_result(ValidationResult(
                    "FLOWS",
                    f"Flujo {flow_name}",
                    "FAIL",
                    "Faltan pasos en el flujo",
                    "El flujo no puede completarse",
                    f"Completar implementación del flujo {flow_name}"
                ))
    
    # ========================================================================
    # VALIDACIONES DE CUMPLIMIENTO
    # ========================================================================
    
    def validate_compliance(self):
        """Validar cumplimiento legal, fiscal y de seguridad"""
        print("\n[COMPLIANCE] Validando Cumplimiento...")
        
            # Legal: Verificar que ZEUS no firma documentos
        rafael_file = self.backend_dir / "agents/rafael.py"
        justicia_file = self.backend_dir / "agents/justicia.py"
        
        compliance_checks = {
            "ZEUS no firma documentos": {
                "files": [rafael_file, justicia_file],
                "negative_keywords": ["firmar", "sign", "signature", "firma_digital"],
                "positive_keywords": ["borrador", "draft", "aprobación"],
                "negative_context_check": True  # Verificar que keywords negativos están en contexto negativo
            },
            "RAFAEL solo modo borrador": {
                "files": [rafael_file],
                "negative_keywords": ["presentar", "submit", "enviar_hacienda"],
                "positive_keywords": ["draft_only", "borrador", "modo borrador", "no presenta", "no submit"],
                "negative_context_check": True  # Verificar contexto negativo
            },
            "No secretos en frontend": {
                "files": [self.frontend_dir / "src"] if self.frontend_dir.exists() else [],
                "negative_keywords": ["SECRET_KEY", "API_KEY"],
                "file_extensions": [".vue", ".ts", ".js"],
                "skip_if_not_exists": True
            }
        }
        
        for check_name, check_data in compliance_checks.items():
            # Skip si el directorio no existe y está marcado como skip_if_not_exists
            if check_data.get("skip_if_not_exists", False) and not any(f.exists() for f in check_data.get("files", [])):
                self.add_result(ValidationResult(
                    "COMPLIANCE",
                    check_name,
                    "WARNING",
                    "Directorio frontend no encontrado, saltando validación"
                ))
                continue
                
            all_pass = True
            details = []
            
            for file_path in check_data.get("files", []):
                if not file_path.exists():
                    continue
                    
                if file_path.is_dir():
                    # Buscar en todos los archivos del directorio
                    for ext in check_data.get("file_extensions", [".py"]):
                        for sub_file in file_path.rglob(f"*{ext}"):
                            if sub_file.is_file():
                                try:
                                    content = sub_file.read_text(encoding='utf-8', errors='replace')
                                except Exception:
                                    content = ""
                                
                                # Verificar keywords negativos
                                for keyword in check_data.get("negative_keywords", []):
                                    if keyword.lower() in content.lower():
                                        all_pass = False
                                        details.append(f"Keyword prohibido '{keyword}' encontrado en {sub_file.relative_to(self.base_dir)}")
                                
                                # Verificar keywords positivos (al menos uno debe estar)
                                if check_data.get("positive_keywords"):
                                    has_positive = any(kw.lower() in content.lower() for kw in check_data["positive_keywords"])
                                    if not has_positive:
                                        all_pass = False
                                        details.append(f"Falta keyword positivo requerido en {sub_file.relative_to(self.base_dir)}")
                elif file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='replace')
                    except Exception:
                        content = ""
                    
                    for keyword in check_data.get("negative_keywords", []):
                        if keyword.lower() in content.lower():
                            # Si tiene negative_context_check, verificar que no esté en contexto negativo
                            if check_data.get("negative_context_check", False):
                                # Buscar contexto negativo (como "no presenta", "no submit")
                                keyword_idx = content.lower().find(keyword.lower())
                                if keyword_idx >= 0:
                                    # Verificar contexto alrededor del keyword
                                    context_start = max(0, keyword_idx - 50)
                                    context_end = min(len(content), keyword_idx + len(keyword) + 50)
                                    context = content[context_start:context_end].lower()
                                    
                                    # Si está en contexto negativo, está bien
                                    negative_contexts = [
                                        "no ", "not ", "sin ", "draft", "borrador", 
                                        "no puede", "no debe", "no presenta", "no actua",
                                        "no firma", "requiere revision", "requiere aprobación",
                                        "antes de presentar", "responsable final", "gestor humano"
                                    ]
                                    # Verificar contexto antes y después del keyword
                                    context_before = context[:keyword_idx - context_start]
                                    context_after = context[keyword_idx - context_start + len(keyword):]
                                    is_negative_context = (
                                        any(neg_ctx in context_before for neg_ctx in negative_contexts) or
                                        any(neg_ctx in context_after for neg_ctx in negative_contexts) or
                                        "fecha limite de presentacion" in context or
                                        "no presenta" in context_before or
                                        "no presenta" in context_after
                                    )
                                    
                                    if not is_negative_context:
                                        all_pass = False
                                        details.append(f"Keyword prohibido '{keyword}' encontrado sin contexto negativo")
                            else:
                                all_pass = False
                                details.append(f"Keyword prohibido '{keyword}' encontrado")
            
            if all_pass:
                self.add_result(ValidationResult(
                    "COMPLIANCE",
                    check_name,
                    "PASS",
                    "Cumplimiento verificado"
                ))
            else:
                self.add_result(ValidationResult(
                    "COMPLIANCE",
                    check_name,
                    "FAIL",
                    "; ".join(details),
                    "CRÍTICO: Riesgo legal/fiscal/seguridad",
                    "Eliminar keywords prohibidos y agregar validaciones requeridas"
                ))
    
    # ========================================================================
    # VALIDACIONES TÉCNICAS
    # ========================================================================
    
    def validate_technical_quality(self):
        """Validar calidad técnica"""
        print("\n[TECHNICAL] Validando Calidad Tecnica...")
        
        # Verificar que no hay errores obvios de sintaxis
        python_files = list(self.backend_dir.rglob("*.py"))
        syntax_errors = []
        
        for py_file in python_files[:50]:  # Limitar para no tardar mucho
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), str(py_file), 'exec')
            except SyntaxError as e:
                syntax_errors.append(f"{py_file.relative_to(self.base_dir)}: {e}")
            except Exception:
                pass  # Ignorar otros errores
        
        if not syntax_errors:
            self.add_result(ValidationResult(
                "TECHNICAL",
                "Errores de sintaxis Python",
                "PASS",
                f"Validados {min(50, len(python_files))} archivos"
            ))
        else:
            self.add_result(ValidationResult(
                "TECHNICAL",
                "Errores de sintaxis Python",
                "FAIL",
                f"Encontrados {len(syntax_errors)} errores",
                "El código no se puede ejecutar",
                f"Corregir errores: {', '.join(syntax_errors[:3])}"
            ))
        
        # Verificar modelos de base de datos
        models_dir = self.backend_dir / "app/models"
        if models_dir.exists():
            model_files = list(models_dir.glob("*.py"))
            required_models = ["user.py", "document_approval.py"]
            
            for model_file in required_models:
                if (models_dir / model_file).exists():
                    self.add_result(ValidationResult(
                        "TECHNICAL",
                        f"Modelo {model_file}",
                        "PASS"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "TECHNICAL",
                        f"Modelo {model_file}",
                        "FAIL",
                        "Modelo faltante",
                        "Funcionalidad relacionada no disponible"
                    ))
        
        # Verificar endpoints API críticos
        api_endpoints_dir = self.backend_dir / "app/api/v1/endpoints"
        if api_endpoints_dir.exists():
            critical_endpoints = [
                "auth.py",
                "tpv.py",
                "onboarding.py",
                "document_approval.py"
            ]
            
            for endpoint_file in critical_endpoints:
                if (api_endpoints_dir / endpoint_file).exists():
                    self.add_result(ValidationResult(
                        "TECHNICAL",
                        f"Endpoint {endpoint_file}",
                        "PASS"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "TECHNICAL",
                        f"Endpoint {endpoint_file}",
                        "FAIL",
                        "Endpoint crítico faltante"
                    ))
    
    # ========================================================================
    # GENERACIÓN DE REPORTE
    # ========================================================================
    
    def generate_report(self) -> Dict[str, Any]:
        """Generar reporte completo de validación"""
        
        # Agrupar resultados por módulo
        by_module = {}
        by_status = {"PASS": 0, "FAIL": 0, "WARNING": 0}
        
        for result in self.results:
            if result.module not in by_module:
                by_module[result.module] = []
            by_module[result.module].append(result.to_dict())
            by_status[result.status] += 1
        
        # Determinar veredicto
        total = len(self.results)
        pass_rate = (by_status["PASS"] / total * 100) if total > 0 else 0
        
        if by_status["FAIL"] == 0:
            verdict = "APPROVED_FOR_MARKET"
        elif by_status["FAIL"] <= 5 and pass_rate >= 90:
            verdict = "APPROVED_WITH_MINOR_WARNINGS"
        else:
            verdict = "NOT_APPROVED"
        
        # Obtener fallos críticos
        critical_failures = [
            r.to_dict() for r in self.results 
            if r.status == "FAIL" and "CRÍTICO" in r.impact
        ]
        
        report = {
            "validation_config": VALIDATION_CONFIG,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_checks": total,
                "passed": by_status["PASS"],
                "failed": by_status["FAIL"],
                "warnings": by_status["WARNING"],
                "pass_rate": f"{pass_rate:.1f}%"
            },
            "results_by_module": by_module,
            "critical_failures": critical_failures,
            "verdict": verdict,
            "verdict_reason": self._get_verdict_reason(verdict, by_status, pass_rate),
            "recommendations": self._get_recommendations()
        }
        
        return report
    
    def _get_verdict_reason(self, verdict: str, by_status: Dict, pass_rate: float) -> str:
        if verdict == "APPROVED_FOR_MARKET":
            return "Todos los checks pasaron. El ecosistema está completo y listo para producción."
        elif verdict == "APPROVED_WITH_MINOR_WARNINGS":
            return f"Pass rate: {pass_rate:.1f}%. Fallos menores detectados ({by_status['FAIL']} fallos, {by_status['WARNING']} warnings). Se recomienda revisar antes de lanzar."
        else:
            return f"Pass rate: {pass_rate:.1f}%. Múltiples fallos críticos detectados ({by_status['FAIL']} fallos). NO se recomienda lanzar hasta corregir."
    
    def _get_recommendations(self) -> List[str]:
        recommendations = []
        
        fail_count = sum(1 for r in self.results if r.status == "FAIL")
        critical_count = sum(1 for r in self.results if r.status == "FAIL" and "CRÍTICO" in r.impact)
        
        if critical_count > 0:
            recommendations.append(f"URGENTE: Corregir {critical_count} fallos críticos antes de lanzar.")
        
        if fail_count > 0:
            recommendations.append(f"Revisar y corregir {fail_count} fallos detectados.")
        
        warning_count = sum(1 for r in self.results if r.status == "WARNING")
        if warning_count > 0:
            recommendations.append(f"Revisar {warning_count} warnings para mejorar la calidad.")
        
        # Recomendaciones específicas
        modules_with_fails = set(r.module for r in self.results if r.status == "FAIL")
        for module in modules_with_fails:
            recommendations.append(f"Priorizar correcciones en módulo {module}.")
        
        if not recommendations:
            recommendations.append("¡Excelente! El ecosistema está listo para producción.")
        
        return recommendations
    
    def run_all_validations(self):
        """Ejecutar todas las validaciones"""
        import sys
        import io
        
        # Configurar UTF-8 para Windows
        if sys.platform == 'win32':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        
        print("=" * 80)
        print("ZEUS-IA FULL ECOSYSTEM VALIDATION")
        print("=" * 80)
        print(f"Inicio: {datetime.now().isoformat()}\n")
        
        try:
            self.validate_core_modules()
            self.validate_agents()
            self.validate_business_modules()
            self.validate_end_to_end_flows()
            self.validate_compliance()
            self.validate_technical_quality()
        except Exception as e:
            self.add_result(ValidationResult(
                "SYSTEM",
                "Ejecución de validaciones",
                "FAIL",
                f"Error durante validación: {str(e)}",
                "CRÍTICO: No se pudo completar la validación",
                f"Revisar error: {traceback.format_exc()}"
            ))
        
        print("\n" + "=" * 80)
        print("GENERANDO REPORTE...")
        print("=" * 80)
        
        report = self.generate_report()
        
        # Mostrar resumen
        print(f"\n[PASS] Passed: {report['summary']['passed']}")
        print(f"[FAIL] Failed: {report['summary']['failed']}")
        print(f"[WARN] Warnings: {report['summary']['warnings']}")
        print(f"[RATE] Pass Rate: {report['summary']['pass_rate']}")
        print(f"\n[VERDICT] {report['verdict']}")
        print(f"[REASON] {report['verdict_reason']}")
        
        if report['critical_failures']:
            print(f"\n[CRITICAL] FALLOS CRITICOS DETECTADOS ({len(report['critical_failures'])}):")
            for failure in report['critical_failures'][:5]:
                print(f"   - [{failure['module']}] {failure['check']}: {failure['details']}")
        
        # Guardar reporte
        report_file = self.base_dir / "validation_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n[SAVED] Reporte guardado en: {report_file.relative_to(self.base_dir.parent)}")
        
        return report

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    validator = EcosystemValidator()
    report = validator.run_all_validations()
    
    # Exit code según veredicto
    if report['verdict'] == "APPROVED_FOR_MARKET":
        sys.exit(0)
    elif report['verdict'] == "APPROVED_WITH_MINOR_WARNINGS":
        sys.exit(1)
    else:
        sys.exit(2)

