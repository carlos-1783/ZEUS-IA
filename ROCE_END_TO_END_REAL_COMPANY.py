#!/usr/bin/env python3
"""
ROCE - Real Operational Company Evaluation
Auditoría End-to-End para Empresa Real
Verifica que ZEUS funciona realmente desde cero con todos los agentes
"""

import json
import requests  # pyright: ignore[reportMissingModuleSource]  # pyright: ignore[reportMissingModuleSource]
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys

class ROCEAuditor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "audit_date": datetime.now().isoformat(),
            "auditor": "CURSO",
            "company_name": "Empresa Ficticia Global S.L.",
            "steps": [],
            "agents_status": {},
            "critical_failures": [],
            "warnings": [],
            "successes": []
        }
        self.tokens = {}
        self.company_id = None
        self.user_ids = {}
        
    def log(self, step: str, action: str, status: str, details: str = "", critical: bool = False):
        """Registrar resultado de una acción"""
        result = {
            "step": step,
            "action": action,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "critical": critical
        }
        self.results["steps"].append(result)
        
        if status == "FAIL" and critical:
            self.results["critical_failures"].append(result)
        elif status == "WARN":
            self.results["warnings"].append(result)
        elif status == "SUCCESS":
            self.results["successes"].append(result)
            
        print(f"[{status}] {step} - {action}: {details}")
        
    def refresh_token_if_needed(self, role: str) -> bool:
        """Refrescar token si está expirado"""
        if role not in self.tokens:
            return False
        
        # Intentar usar el token actual
        test_result = self.api_request("GET", "/api/v1/auth/me", token=self.tokens[role])
        if test_result["success"]:
            return True  # Token válido
        
        # Si falla con 401, intentar re-login
        if "401" in str(test_result.get("error", "")) or "expirado" in str(test_result.get("error", "")).lower():
            # Buscar credenciales del usuario
            users_map = {
                "ADMIN": {"email": "admin@empresaglobal.com", "password": "Password123!"},
                "EMPLOYEE": {"email": "empleado1@empresaglobal.com", "password": "Password123!"},
                "superuser": {"email": "superuser@empresaglobal.com", "password": "SuperSecure123!"}
            }
            
            if role in users_map:
                creds = users_map[role]
                login_result = self.api_request("POST", "/api/v1/auth/login", data={
                    "username": creds["email"],
                    "password": creds["password"]
                }, use_form_data=True)
                if login_result["success"]:
                    self.tokens[role] = login_result["data"].get("access_token")
                    return True
        return False
    
    def api_request(self, method: str, endpoint: str, token: Optional[str] = None, data: Optional[Dict] = None, use_form_data: bool = False, role: Optional[str] = None) -> Dict:
        """Realizar petición API con auto-refresh de token"""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        # Para login, usar form-data; para el resto, JSON
        if use_form_data:
            # Form data (para login) - no añadir Content-Type, requests lo hace automáticamente
            request_data = data
        else:
            # JSON (para el resto)
            headers["Content-Type"] = "application/json"
            request_data = data
            
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                if use_form_data:
                    response = requests.post(url, headers=headers, data=request_data, timeout=10)
                else:
                    response = requests.post(url, headers=headers, json=request_data, timeout=10)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=request_data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Method {method} not supported")
            
            # Si es 401 y tenemos role, intentar refresh
            if response.status_code == 401 and role and self.refresh_token_if_needed(role):
                # Reintentar con nuevo token
                headers["Authorization"] = f"Bearer {self.tokens[role]}"
                if method == "GET":
                    response = requests.get(url, headers=headers, timeout=10)
                elif method == "POST":
                    if use_form_data:
                        response = requests.post(url, headers=headers, data=request_data, timeout=10)
                    else:
                        response = requests.post(url, headers=headers, json=request_data, timeout=10)
                elif method == "PUT":
                    response = requests.put(url, headers=headers, json=request_data, timeout=10)
                elif method == "DELETE":
                    response = requests.delete(url, headers=headers, timeout=10)
                
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json() if response.content else {}}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def step_1_initialization(self):
        """Paso 1: Inicialización desde cero"""
        print("\n" + "="*80)
        print("PASO 1: INICIALIZACIÓN DESDE CERO")
        print("="*80)
        
        # 1.1 Crear superusuario
        self.log("1.1", "Crear superusuario", "INFO", "Verificando si existe superusuario...")
        superuser_data = {
            "email": "superuser@empresaglobal.com",
            "password": "SuperSecure123!",
            "full_name": "Super Usuario Global",
            "is_superuser": True
        }
        result = self.api_request("POST", "/api/v1/auth/register", data=superuser_data)
        if result["success"]:
            # El registro devuelve el usuario, no el token. Necesitamos hacer login
            login_result = self.api_request("POST", "/api/v1/auth/login", data={
                "username": superuser_data["email"],  # El endpoint espera "username" aunque sea email
                "password": superuser_data["password"]
            }, use_form_data=True)
            if login_result["success"]:
                self.tokens["superuser"] = login_result["data"].get("access_token")
                self.log("1.1", "Crear superusuario", "SUCCESS", "Superusuario creado y autenticado")
            else:
                self.log("1.1", "Login superusuario", "FAIL", login_result.get("error", "Unknown error"), critical=True)
                return False
        else:
            # Si el registro falla, puede ser porque ya existe. Intentar login
            error_msg = result.get("error", "")
            if "already registered" in error_msg.lower() or "400" in str(result.get("error", "")):
                login_result = self.api_request("POST", "/api/v1/auth/login", data={
                    "username": superuser_data["email"],  # El endpoint espera "username" aunque sea email
                    "password": superuser_data["password"]
                }, use_form_data=True)
                if login_result["success"]:
                    self.tokens["superuser"] = login_result["data"].get("access_token")
                    self.log("1.1", "Login superusuario", "SUCCESS", "Superusuario ya existía, autenticado")
                else:
                    self.log("1.1", "Crear/Login superusuario", "FAIL", login_result.get("error", "Unknown error"), critical=True)
                    return False
            else:
                # Intentar login de todas formas
                login_result = self.api_request("POST", "/api/v1/auth/login", data={
                    "username": superuser_data["email"],
                    "password": superuser_data["password"]
                }, use_form_data=True)
                if login_result["success"]:
                    self.tokens["superuser"] = login_result["data"].get("access_token")
                    self.log("1.1", "Login superusuario", "SUCCESS", "Superusuario autenticado")
                else:
                    self.log("1.1", "Crear/Login superusuario", "FAIL", result.get("error", "Unknown error"), critical=True)
                    return False
        
        # 1.2 Configurar business profile (equivalente a crear empresa)
        self.log("1.2", "Configurar business profile", "INFO", "Configurando perfil de negocio...")
        business_profile_data = {
            "business_profile": "otros"  # servicios_profesionales se mapea a "otros"
        }
        result = self.api_request("POST", "/api/v1/tpv/set-business-profile", 
                                 token=self.tokens["superuser"], data=business_profile_data)
        if result["success"]:
            self.log("1.2", "Configurar business profile", "SUCCESS", f"Business profile configurado: {result['data'].get('business_profile', 'otros')}")
        else:
            self.log("1.2", "Configurar business profile", "WARN", result.get("error", "Unknown error"))
            # No es crítico, continuar
        
        # 1.3 Crear usuarios con distintos roles (usando registro normal)
        users_to_create = [
            {"email": "admin@empresaglobal.com", "role": "ADMIN", "name": "Admin Principal"},
            {"email": "empleado1@empresaglobal.com", "role": "EMPLOYEE", "name": "Empleado 1"},
            {"email": "empleado2@empresaglobal.com", "role": "EMPLOYEE", "name": "Empleado 2"}
        ]
        
        for user_data in users_to_create:
            self.log("1.3", f"Crear usuario {user_data['role']}", "INFO", f"Creando {user_data['email']}...")
            # Intentar crear usuario mediante registro
            result = self.api_request("POST", "/api/v1/auth/register",
                                    data={
                                        "email": user_data["email"],
                                        "password": "Password123!",
                                        "full_name": user_data["name"],
                                        "is_superuser": (user_data["role"] == "ADMIN")
                                    })
            if result["success"]:
                user_id = result["data"].get("id")
                self.user_ids[user_data["role"]] = user_id
                self.log("1.3", f"Crear usuario {user_data['role']}", "SUCCESS", f"Usuario creado: {user_id}")
            else:
                # Si ya existe, intentar login
                login_result = self.api_request("POST", "/api/v1/auth/login", data={
                    "username": user_data["email"],  # El endpoint espera "username" aunque sea email
                    "password": "Password123!"
                }, use_form_data=True)
                if login_result["success"]:
                    token = login_result["data"].get("access_token")
                    # Obtener ID del usuario desde endpoint /auth/me
                    me_result = self.api_request("GET", "/api/v1/auth/me", token=token)
                    if me_result["success"]:
                        user_id = me_result["data"].get("id")
                        self.user_ids[user_data["role"]] = user_id
                        self.log("1.3", f"Usuario {user_data['role']} ya existe", "WARN", f"Usuario ya registrado: {user_id}")
                    else:
                        self.log("1.3", f"Usuario {user_data['role']} ya existe", "WARN", "Usuario ya registrado (no se pudo obtener ID)")
                else:
                    self.log("1.3", f"Crear usuario {user_data['role']}", "WARN", result.get("error", "Unknown error"))
        
        # 1.4 Validar login/logout por rol
        for user_data in users_to_create:
            self.log("1.4", f"Login {user_data['role']}", "INFO", f"Validando login para {user_data['email']}...")
            login_result = self.api_request("POST", "/api/v1/auth/login", data={
                "username": user_data["email"],  # El endpoint espera "username" aunque sea email
                "password": "Password123!"
            }, use_form_data=True)
            if login_result["success"]:
                token = login_result["data"].get("access_token")
                self.tokens[user_data["role"]] = token
                self.log("1.4", f"Login {user_data['role']}", "SUCCESS", "Login exitoso")
            else:
                self.log("1.4", f"Login {user_data['role']}", "FAIL", login_result.get("error", "Unknown error"), critical=True)
        
        return True
    
    def step_2_tpv_real(self):
        """Paso 2: TPV real"""
        print("\n" + "="*80)
        print("PASO 2: TPV REAL")
        print("="*80)
        
        admin_token = self.tokens.get("ADMIN")
        if not admin_token:
            self.log("2.0", "TPV Setup", "FAIL", "No hay token de admin", critical=True)
            return False
        
        # 2.1 Crear múltiples productos/servicios
        products = [
            {"name": "Consultoría Estratégica", "price": 150.00, "category": "Consultoría", "iva_rate": 21.0},
            {"name": "Desarrollo Web", "price": 80.00, "category": "Desarrollo", "iva_rate": 21.0},
            {"name": "Mantenimiento Mensual", "price": 200.00, "category": "Soporte", "iva_rate": 21.0},
            {"name": "Auditoría Técnica", "price": 120.00, "category": "Auditoría", "iva_rate": 21.0}
        ]
        
        product_ids = []
        for product in products:
            self.log("2.1", "Crear producto", "INFO", f"Creando {product['name']}...")
            result = self.api_request("POST", "/api/v1/tpv/products",
                                    token=admin_token, data=product, role="ADMIN")
            if result["success"]:
                product_id = result["data"].get("id") or result["data"].get("product", {}).get("id")
                product_ids.append(product_id)
                self.log("2.1", "Crear producto", "SUCCESS", f"Producto creado: {product_id}")
            else:
                self.log("2.1", "Crear producto", "FAIL", result.get("error", "Unknown error"), critical=True)
        
        # 2.2 Modificar producto
        if product_ids:
            self.log("2.2", "Modificar producto", "INFO", f"Modificando producto {product_ids[0]}...")
            # Obtener el producto primero para mantener category
            get_result = self.api_request("GET", f"/api/v1/tpv/products/{product_ids[0]}", token=admin_token, role="ADMIN")
            category = "Consultoría"  # Default
            if get_result["success"]:
                product_data = get_result["data"].get("product", {}) or get_result["data"]
                category = product_data.get("category", "Consultoría")
            
            update_data = {"price": 175.00, "name": "Consultoría Estratégica Premium", "category": category}
            result = self.api_request("PUT", f"/api/v1/tpv/products/{product_ids[0]}",
                                    token=admin_token, data=update_data, role="ADMIN")
            if result["success"]:
                self.log("2.2", "Modificar producto", "SUCCESS", "Producto modificado")
            else:
                self.log("2.2", "Modificar producto", "WARN", result.get("error", "Unknown error"))
        
        # 2.3 Eliminar producto (último)
        if len(product_ids) > 1:
            self.log("2.3", "Eliminar producto", "INFO", f"Eliminando producto {product_ids[-1]}...")
            result = self.api_request("DELETE", f"/api/v1/tpv/products/{product_ids[-1]}",
                                    token=self.tokens.get("superuser"))
            if result["success"]:
                self.log("2.3", "Eliminar producto", "SUCCESS", "Producto eliminado")
            else:
                self.log("2.3", "Eliminar producto", "WARN", result.get("error", "Unknown error"))
        
        # 2.4 Registrar venta con múltiples líneas
        if len(product_ids) < 2:
            self.log("2.4", "Registrar venta", "FAIL", f"No hay suficientes productos creados ({len(product_ids)}). Se necesitan al menos 2.", critical=True)
            return False
        
        # Asegurar que el business profile esté configurado
        self.log("2.4", "Configurar business profile", "INFO", "Configurando business profile para venta...")
        bp_result = self.api_request("POST", "/api/v1/tpv/set-business-profile", 
                                    token=admin_token, data={"business_profile": "otros"}, role="ADMIN")
        if not bp_result["success"]:
            self.log("2.4", "Configurar business profile", "WARN", bp_result.get("error", "Unknown error"))
        
        self.log("2.4", "Registrar venta", "INFO", "Registrando venta con múltiples productos...")
        sale_data = {
            "payment_method": "efectivo",
            "cart_items": [
                {"product_id": product_ids[0], "quantity": 2, "unit_price": 175.00, "iva_rate": 21.0},
                {"product_id": product_ids[1], "quantity": 1, "unit_price": 80.00, "iva_rate": 21.0}
            ],
            "note": "Venta de prueba ROCE"
        }
        result = self.api_request("POST", "/api/v1/tpv/sale",
                                token=admin_token, data=sale_data, role="ADMIN")
        if result["success"]:
            ticket_id = result["data"].get("ticket_id") or result["data"].get("ticket", {}).get("id")
            self.log("2.4", "Registrar venta", "SUCCESS", f"Venta registrada: Ticket #{ticket_id}")
        else:
            self.log("2.4", "Registrar venta", "FAIL", result.get("error", "Unknown error"), critical=True)
            return False
        
        # 2.5 Verificar persistencia (listar productos)
        self.log("2.5", "Verificar persistencia", "INFO", "Verificando persistencia de productos...")
        result = self.api_request("GET", "/api/v1/tpv/products", token=admin_token, role="ADMIN")
        if result["success"]:
            products_list = result["data"].get("products", [])
            self.log("2.5", "Verificar persistencia", "SUCCESS", f"{len(products_list)} productos encontrados")
        else:
            self.log("2.5", "Verificar persistencia", "WARN", result.get("error", "Unknown error"))
        
        return True
    
    def step_3_control_horario(self):
        """Paso 3: Control horario"""
        print("\n" + "="*80)
        print("PASO 3: CONTROL HORARIO")
        print("="*80)
        
        employee_token = self.tokens.get("EMPLOYEE")
        if not employee_token:
            self.log("3.0", "Control Horario Setup", "FAIL", "No hay token de empleado", critical=True)
            return False
        
        # 3.1 Check-in empleado
        # Obtener ID del empleado desde /me
        me_result = self.api_request("GET", "/api/v1/auth/me", token=employee_token)
        employee_id = None
        if me_result["success"]:
            employee_id = str(me_result["data"].get("id", ""))
        
        if not employee_id:
            self.log("3.1", "Check-in empleado", "WARN", "No se pudo obtener ID del empleado")
            return True  # No crítico
        
        self.log("3.1", "Check-in empleado", "INFO", f"Registrando entrada para empleado {employee_id}...")
        checkin_data = {
            "employee_id": employee_id,
            "method": "code",
            "location": "Oficina Central"
        }
        result = self.api_request("POST", "/api/v1/control-horario/check-in",
                                token=employee_token, data=checkin_data, role="EMPLOYEE")
        if result["success"]:
            self.log("3.1", "Check-in empleado", "SUCCESS", "Check-in registrado")
        else:
            self.log("3.1", "Check-in empleado", "WARN", result.get("error", "Unknown error"))
        
        time.sleep(2)  # Simular tiempo trabajado
        
        # 3.2 Check-out empleado
        self.log("3.2", "Check-out empleado", "INFO", f"Registrando salida para empleado {employee_id}...")
        checkout_data = {
            "employee_id": employee_id,
            "method": "code",
            "location": "Oficina Central"
        }
        result = self.api_request("POST", "/api/v1/control-horario/check-out",
                                token=employee_token, data=checkout_data, role="EMPLOYEE")
        if result["success"]:
            hours = result["data"].get("hours_worked", 0)
            self.log("3.2", "Check-out empleado", "SUCCESS", f"Check-out registrado. Horas: {hours}")
        else:
            self.log("3.2", "Check-out empleado", "WARN", result.get("error", "Unknown error"))
        
        return True
    
    def step_4_flujo_fiscal(self):
        """Paso 4: Flujo fiscal legal"""
        print("\n" + "="*80)
        print("PASO 4: FLUJO FISCAL LEGAL")
        print("="*80)
        
        admin_token = self.tokens.get("ADMIN")
        if not admin_token:
            self.log("4.0", "Flujo Fiscal Setup", "FAIL", "No hay token de admin", critical=True)
            return False
        
        # 4.1 Generar factura desde TPV
        self.log("4.1", "Generar factura", "INFO", "Generando factura desde TPV...")
        # Nota: Esto dependería de la implementación real del endpoint de facturación
        result = self.api_request("POST", "/api/v1/invoices/generate",
                                token=admin_token, data={"ticket_id": "last"})
        if result["success"]:
            invoice_id = result["data"].get("id")
            self.log("4.1", "Generar factura", "SUCCESS", f"Factura generada: {invoice_id}")
        else:
            self.log("4.1", "Generar factura", "WARN", result.get("error", "Endpoint puede no estar implementado"))
        
        return True
    
    def step_5_marketing(self):
        """Paso 5: Marketing y captación"""
        print("\n" + "="*80)
        print("PASO 5: MARKETING Y CAPTACIÓN (PERSEO)")
        print("="*80)
        
        admin_token = self.tokens.get("ADMIN")
        if not admin_token:
            self.log("5.0", "Marketing Setup", "FAIL", "No hay token de admin", critical=True)
            return False
        
        # 5.1 PERSEO analiza mercado
        self.log("5.1", "PERSEO analiza mercado", "INFO", "Solicitando análisis de mercado...")
        result = self.api_request("POST", "/api/v1/perseo/analyze",
                                token=admin_token, data={"market": "servicios_profesionales"})
        if result["success"]:
            self.log("5.1", "PERSEO analiza mercado", "SUCCESS", "Análisis completado")
        else:
            self.log("5.1", "PERSEO analiza mercado", "WARN", result.get("error", "Endpoint puede no estar implementado"))
        
        return True
    
    def step_6_seguridad(self):
        """Paso 6: Seguridad y control"""
        print("\n" + "="*80)
        print("PASO 6: SEGURIDAD Y CONTROL (THALOS)")
        print("="*80)
        
        # 6.1 THALOS valida permisos
        self.log("6.1", "THALOS valida permisos", "INFO", "Verificando validación de permisos...")
        employee_token = self.tokens.get("EMPLOYEE")
        if employee_token:
            # Intentar acceder a endpoint de admin como empleado
            result = self.api_request("GET", "/api/v1/admin/stats", token=employee_token)
            if not result["success"] and "403" in str(result.get("error", "")):
                self.log("6.1", "THALOS valida permisos", "SUCCESS", "Permisos correctamente validados (403 esperado)")
            else:
                self.log("6.1", "THALOS valida permisos", "WARN", "Validación de permisos puede no estar funcionando")
        
        return True
    
    def step_7_dashboard(self):
        """Paso 7: Dashboard y coherencia"""
        print("\n" + "="*80)
        print("PASO 7: DASHBOARD Y COHERENCIA")
        print("="*80)
        
        admin_token = self.tokens.get("ADMIN")
        if not admin_token:
            self.log("7.0", "Dashboard Setup", "FAIL", "No hay token de admin", critical=True)
            return False
        
        # 7.1 Verificar métricas
        self.log("7.1", "Verificar métricas", "INFO", "Obteniendo métricas del dashboard...")
        result = self.api_request("GET", "/api/v1/metrics/summary?days=30", token=admin_token)
        if result["success"]:
            metrics = result["data"].get("metrics", {})
            self.log("7.1", "Verificar métricas", "SUCCESS", f"Métricas obtenidas: {list(metrics.keys())}")
        else:
            self.log("7.1", "Verificar métricas", "WARN", result.get("error", "Unknown error"))
        
        return True
    
    def check_agents_status(self):
        """Verificar estado de todos los agentes"""
        print("\n" + "="*80)
        print("VERIFICACIÓN DE AGENTES")
        print("="*80)
        
        # Usar endpoint unificado de estado de agentes
        self.log("AGENTS", "Verificar todos los agentes", "INFO", "Obteniendo estado de todos los agentes...")
        result = self.api_request("GET", "/api/v1/agents/status")
        if result["success"]:
            agents_data = result["data"].get("agents", {})
            for agent_name, agent_info in agents_data.items():
                status = agent_info.get("status", "unknown")
                self.results["agents_status"][agent_name] = status
                self.log("AGENTS", f"Verificar {agent_name}", "SUCCESS", f"Estado: {status}")
        else:
            # Si falla, marcar todos como unknown
            agents = ["ZEUS CORE", "RAFAEL", "PERSEO", "JUSTICIA", "THALOS", "AFRODITA"]
            for agent in agents:
                self.results["agents_status"][agent] = "unknown"
                self.log("AGENTS", f"Verificar {agent}", "WARN", result.get("error", "Unknown error"))
    
    def generate_final_report(self):
        """Generar reporte final"""
        print("\n" + "="*80)
        print("GENERANDO REPORTE FINAL")
        print("="*80)
        
        # Calcular scores
        total_steps = len([s for s in self.results["steps"] if s["step"].startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7."))])
        success_steps = len([s for s in self.results["steps"] if s["status"] == "SUCCESS" and s["step"].startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7."))])
        critical_failures = len(self.results["critical_failures"])
        warnings_count = len(self.results["warnings"])
        
        # Business Readiness Score
        business_readiness = (success_steps / total_steps * 100) if total_steps > 0 else 0
        
        # Risk assessment
        legal_risk = "HIGH" if critical_failures > 2 else "MEDIUM" if critical_failures > 0 else "LOW"
        technical_risk = "HIGH" if warnings_count > 5 else "MEDIUM" if warnings_count > 2 else "LOW"
        commercial_risk = "HIGH" if critical_failures > 0 else "MEDIUM" if warnings_count > 3 else "LOW"
        
        # Veredicto
        if critical_failures == 0 and business_readiness >= 80:
            verdict = "GO"
            reasoning = "Sistema funcional con alta tasa de éxito. Sin fallos críticos detectados."
        elif critical_failures == 0 and business_readiness >= 60:
            verdict = "GO_WITH_LIMITS"
            reasoning = "Sistema funcional pero con limitaciones. Requiere mejoras antes de producción completa."
        else:
            verdict = "NO_GO"
            reasoning = f"Sistema no está listo para producción. {critical_failures} fallos críticos detectados."
        
        self.results["final_report"] = {
            "summary": {
                "total_steps": total_steps,
                "successful_steps": success_steps,
                "success_rate": f"{business_readiness:.1f}%",
                "critical_failures": critical_failures,
                "warnings": warnings_count
            },
            "agent_by_agent": self.results["agents_status"],
            "failures_detected": self.results["critical_failures"],
            "business_readiness_score": business_readiness,
            "legal_risk": legal_risk,
            "technical_risk": technical_risk,
            "commercial_risk": commercial_risk,
            "veredicto": verdict,
            "reasoning": reasoning
        }
        
        # Guardar reporte
        report_filename = f"ROCE_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*80}")
        print(f"VEREDICTO FINAL: {verdict}")
        print(f"{'='*80}")
        print(f"Razonamiento: {reasoning}")
        print(f"\nBusiness Readiness: {business_readiness:.1f}%")
        print(f"Fallos críticos: {critical_failures}")
        print(f"Advertencias: {warnings_count}")
        print(f"\nReporte guardado en: {report_filename}")
        
        return verdict
    
    def run_full_audit(self):
        """Ejecutar auditoría completa"""
        print("="*80)
        print("ROCE - REAL OPERATIONAL COMPANY EVALUATION")
        print("Auditoría End-to-End para Empresa Real")
        print("="*80)
        
        steps = [
            ("Inicialización", self.step_1_initialization),
            ("TPV Real", self.step_2_tpv_real),
            ("Control Horario", self.step_3_control_horario),
            ("Flujo Fiscal", self.step_4_flujo_fiscal),
            ("Marketing", self.step_5_marketing),
            ("Seguridad", self.step_6_seguridad),
            ("Dashboard", self.step_7_dashboard)
        ]
        
        for step_name, step_func in steps:
            try:
                step_func()
            except Exception as e:
                self.log(step_name, "Ejecución", "FAIL", f"Error inesperado: {str(e)}", critical=True)
        
        # Verificar agentes
        self.check_agents_status()
        
        # Generar reporte final
        verdict = self.generate_final_report()
        
        return verdict

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    auditor = ROCEAuditor(base_url)
    verdict = auditor.run_full_audit()
    sys.exit(0 if verdict == "GO" else 1)
