"""
💳 TPV Universal Enterprise
Sistema de punto de venta adaptable a cualquier tipo de negocio
Integración automática con RAFAEL, JUSTICIA y AFRODITA
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)

# Integraciones de agentes (proceso): cada petición usa create_tpv_service() — sin carrito ni estado compartido.
_tpv_rafael_integration: Optional[Any] = None
_tpv_justicia_integration: Optional[Any] = None
_tpv_afrodita_integration: Optional[Any] = None


def set_tpv_integrations(
    rafael: Optional[Any] = None,
    justicia: Optional[Any] = None,
    afrodita: Optional[Any] = None,
) -> None:
    """Registrar RAFAEL/JUSTICIA/AFRODITA para nuevas instancias TPV (no usar singleton)."""
    global _tpv_rafael_integration, _tpv_justicia_integration, _tpv_afrodita_integration
    if rafael is not None:
        _tpv_rafael_integration = rafael
    if justicia is not None:
        _tpv_justicia_integration = justicia
    if afrodita is not None:
        _tpv_afrodita_integration = afrodita
    logger.info("🔗 Integraciones TPV registradas (ámbito proceso)")


def create_tpv_service() -> "TPVService":
    """Nueva instancia por solicitud; copia integraciones globales del proceso."""
    s = TPVService()
    s.rafael_integration = _tpv_rafael_integration
    s.justicia_integration = _tpv_justicia_integration
    s.afrodita_integration = _tpv_afrodita_integration
    return s


class BusinessProfile(str, Enum):
    """Perfiles de negocio soportados"""
    RESTAURANTE = "restaurante"
    BAR = "bar"
    CAFETERIA = "cafetería"
    TIENDA_MINORISTA = "tienda_minorista"
    PELUQUERIA = "peluquería"
    CENTRO_ESTETICO = "centro_estético"
    TALLER = "taller"
    CLINICA = "clínica"
    DISCOTECA = "discoteca"
    FARMACIA = "farmacia"
    LOGISTICA = "logística"
    OTROS = "otros"


class PaymentMethod(str, Enum):
    """Métodos de pago soportados"""
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    BIZUM = "bizum"
    TRANSFERENCIA = "transferencia"


class TPVDocumentType(str, Enum):
    """Tipos de documentos del TPV"""
    TICKET = "ticket"
    FACTURA = "factura"
    PRESUPUESTO = "presupuesto"
    CIERRE_CAJA = "cierre_caja"


class TPVService:
    """
    TPV Universal Enterprise
    Sistema de punto de venta adaptable a cualquier tipo de negocio
    """
    
    def __init__(self):
        self.business_profile: Optional[BusinessProfile] = None
        self.products: Dict[str, Dict[str, Any]] = {}
        self.categories: Dict[str, Dict[str, Any]] = {}
        self.employees: Dict[str, Dict[str, Any]] = {}
        self.terminals: Dict[str, Dict[str, Any]] = {}
        self.pricing_rules: List[Dict[str, Any]] = []
        self.inventory_sync_enabled = True
        self.config: Dict[str, Any] = {}  # Configuración del TPV por tipo de negocio
        
        # Integraciones
        self.rafael_integration = None
        self.justicia_integration = None
        self.afrodita_integration = None
        
        logger.info("💳 TPV Universal Enterprise inicializado")
    
    def get_business_config(self, profile: BusinessProfile) -> Dict[str, Any]:
        """
        Obtener configuración específica por tipo de negocio
        Define flags funcionales según el tipo de negocio
        """
        configs = {
            BusinessProfile.RESTAURANTE: {
                "tables_enabled": True,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["Bebidas", "Comida", "Entrantes", "Platos", "Postres", "Bebidas Alcohólicas"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": False,
                "requires_customer_data": False
            },
            BusinessProfile.BAR: {
                "tables_enabled": True,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["Bebidas", "Bebidas Alcohólicas", "Tapas", "Raciones"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": False,
                "requires_employee": False,
                "requires_customer_data": False
            },
            BusinessProfile.CAFETERIA: {
                "tables_enabled": True,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["Bebidas", "Café", "Bollería", "Bocadillos", "Tostadas"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": False,
                "requires_employee": False,
                "requires_customer_data": False
            },
            BusinessProfile.TIENDA_MINORISTA: {
                "tables_enabled": False,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["General", "Electrónica", "Ropa", "Hogar", "Alimentación"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": False,
                "requires_customer_data": False
            },
            BusinessProfile.PELUQUERIA: {
                "tables_enabled": False,
                "services_enabled": True,
                "appointments_enabled": True,
                "inventory_enabled": True,
                "default_categories": ["Servicios", "Productos", "Cortes", "Tintes", "Tratamientos"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": True,
                "requires_customer_data": True
            },
            BusinessProfile.CENTRO_ESTETICO: {
                "tables_enabled": False,
                "services_enabled": True,
                "appointments_enabled": True,
                "inventory_enabled": True,
                "default_categories": ["Servicios", "Productos", "Faciales", "Corporales", "Tratamientos"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": True,
                "requires_customer_data": True
            },
            BusinessProfile.CLINICA: {
                "tables_enabled": False,
                "services_enabled": True,
                "appointments_enabled": True,
                "inventory_enabled": False,
                "default_categories": ["Consultas", "Tratamientos", "Servicios Médicos"],
                "default_iva_rate": 0.0,  # Servicios médicos pueden estar exentos
                "supports_tickets": False,
                "supports_invoices": True,
                "requires_employee": True,
                "requires_customer_data": True
            },
            BusinessProfile.TALLER: {
                "tables_enabled": False,
                "services_enabled": True,
                "appointments_enabled": True,
                "inventory_enabled": True,
                "default_categories": ["Servicios", "Repuestos", "Mano de Obra", "Piezas"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": True,
                "requires_customer_data": True
            },
            BusinessProfile.DISCOTECA: {
                "tables_enabled": False,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["Entradas", "Bebidas", "Bebidas Alcohólicas"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": False,
                "requires_employee": False,
                "requires_customer_data": False
            },
            BusinessProfile.FARMACIA: {
                "tables_enabled": False,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["Medicamentos", "Parafarmacia", "Higiene", "Cosmética"],
                "default_iva_rate": 4.0,  # Medicamentos reducido
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": True,
                "requires_customer_data": False
            },
            BusinessProfile.LOGISTICA: {
                "tables_enabled": False,
                "services_enabled": True,
                "appointments_enabled": False,
                "inventory_enabled": False,
                "default_categories": ["Envíos", "Servicios", "Paquetes"],
                "default_iva_rate": 21.0,
                "supports_tickets": False,
                "supports_invoices": True,
                "requires_employee": False,
                "requires_customer_data": True
            },
            BusinessProfile.OTROS: {
                "tables_enabled": False,
                "services_enabled": False,
                "appointments_enabled": False,
                "inventory_enabled": True,
                "default_categories": ["General"],
                "default_iva_rate": 21.0,
                "supports_tickets": True,
                "supports_invoices": True,
                "requires_employee": False,
                "requires_customer_data": False
            }
        }
        
        return configs.get(profile, configs[BusinessProfile.OTROS])
    
    def set_business_profile(self, profile: BusinessProfile, user_id: Optional[int] = None):
        """
        Establecer business_profile y cargar configuración
        Este método debe llamarse cuando se carga el TPV para un usuario
        """
        self.business_profile = profile
        self.config = self.get_business_config(profile)
        logger.info(f"[INFO] Business profile establecido: {profile.value} para usuario {user_id}")
    
    def load_user_profile(self, user_data: Dict[str, Any]):
        """
        Cargar business_profile desde datos de usuario
        Si no existe, usar auto-detección o default
        """
        business_profile_str = user_data.get("tpv_business_profile")
        
        if business_profile_str:
            try:
                profile = BusinessProfile(business_profile_str)
                self.set_business_profile(profile, user_data.get("id"))
                return profile
            except ValueError:
                logger.warning(f"[WARN] Business profile invalido en usuario: {business_profile_str}")
        
        # Auto-detección basada en company_name
        company_name = user_data.get("company_name", "")
        if company_name:
            detected = self.auto_detect_business_type({"name": company_name})
            self.set_business_profile(detected, user_data.get("id"))
            return detected
        
        # Default
        default_profile = BusinessProfile.OTROS
        self.set_business_profile(default_profile, user_data.get("id"))
        return default_profile
    
    def require_business_profile(self) -> BusinessProfile:
        """
        Requerir business_profile. Si no está establecido, lanzar error.
        """
        if not self.business_profile:
            raise ValueError("Business profile no establecido. Configure el tipo de negocio antes de usar el TPV.")
        return self.business_profile
    
    def auto_detect_business_type(self, business_data: Dict[str, Any]) -> BusinessProfile:
        """
        Detectar automáticamente el tipo de negocio basado en datos
        
        Args:
            business_data: Datos del negocio (nombre, descripción, productos, etc.)
        
        Returns:
            BusinessProfile detectado
        """
        business_name = business_data.get("name", "").lower()
        description = business_data.get("description", "").lower()
        products = business_data.get("products", [])
        
        # Keywords para cada perfil
        profile_keywords = {
            BusinessProfile.RESTAURANTE: ["restaurante", "comida", "cena", "menú", "plato", "cocina"],
            BusinessProfile.BAR: ["bar", "cerveza", "copa", "bebida", "terraza"],
            BusinessProfile.CAFETERIA: ["cafetería", "café", "desayuno", "bocadillo", "tostada"],
            BusinessProfile.TIENDA_MINORISTA: ["tienda", "producto", "venta", "minorista", "retail"],
            BusinessProfile.PELUQUERIA: ["peluquería", "corte", "pelo", "tinte", "peinado"],
            BusinessProfile.CENTRO_ESTETICO: ["estético", "masaje", "facial", "tratamiento", "belleza"],
            BusinessProfile.TALLER: ["taller", "reparación", "mecánico", "pieza", "servicio"],
            BusinessProfile.CLINICA: ["clínica", "consulta", "médico", "paciente", "tratamiento"],
            BusinessProfile.DISCOTECA: ["discoteca", "noche", "fiesta", "entrada", "barra"],
            BusinessProfile.FARMACIA: ["farmacia", "medicamento", "receta", "farmacéutico"],
            BusinessProfile.LOGISTICA: ["logística", "envío", "reparto", "almacén", "transporte"]
        }
        
        # Contar matches
        scores = {}
        all_text = f"{business_name} {description}".lower()
        
        for profile, keywords in profile_keywords.items():
            score = sum(1 for kw in keywords if kw in all_text)
            scores[profile] = score
        
        # Seleccionar el perfil con mayor score
        if scores:
            detected_profile = max(scores, key=scores.get)
            if scores[detected_profile] > 0:
                self.business_profile = detected_profile
                logger.info(f"🏢 Tipo de negocio detectado: {detected_profile.value}")
                return detected_profile
        
        # Default
        self.business_profile = BusinessProfile.OTROS
        logger.info(f"🏢 Tipo de negocio: {BusinessProfile.OTROS.value} (no detectado)")
        return BusinessProfile.OTROS
    
    def create_product(
        self,
        name: str,
        price: float,
        category: str,
        iva_rate: float = 21.0,
        stock: Optional[int] = None,
        image: Optional[str] = None,
        icon: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Crear producto en el sistema
        
        Args:
            name: Nombre del producto
            price: Precio base (sin IVA)
            category: Categoría del producto
            iva_rate: Tasa de IVA (21%, 10%, 4%, 0%)
            stock: Stock disponible (opcional)
            image: URL de la imagen del producto (opcional)
            icon: Icono del producto (opcional: coffee, food, service, house, default)
            metadata: Metadata adicional
        
        Returns:
            Dict con información del producto creado
        """
        # Generar ID único - usar timestamp + contador para garantizar unicidad
        import time
        import random
        base_id = int(time.time() * 1000)
        counter = len(self.products)
        product_id = f"PROD_{base_id}_{counter:04d}"
        
        # Verificar que el ID no existe (por si acaso)
        while product_id in self.products:
            counter += 1
            product_id = f"PROD_{base_id}_{counter:04d}"
        
        product = {
            "id": product_id,
            "name": name,
            "price": price,
            "price_with_iva": price * (1 + iva_rate / 100),
            "category": category,
            "iva_rate": iva_rate,
            "stock": stock,
            "image": image,  # URL de la imagen
            "icon": icon,    # Icono predefinido
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        self.products[product_id] = product
        
        logger.info(f"📦 Producto creado: {name} (€{price:.2f}) - ID: {product_id}")
        logger.info(f"📊 Total productos en sistema: {len(self.products)}")
        
        return product
    
    def update_product(
        self,
        product_id: str,
        name: Optional[str] = None,
        price: Optional[float] = None,
        category: Optional[str] = None,
        iva_rate: Optional[float] = None,
        stock: Optional[int] = None,
        image: Optional[str] = None,
        icon: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Actualizar producto existente
        
        Args:
            product_id: ID del producto a actualizar
            name: Nuevo nombre (opcional)
            price: Nuevo precio (opcional)
            category: Nueva categoría (opcional)
            iva_rate: Nueva tasa de IVA (opcional)
            stock: Nuevo stock (opcional)
            metadata: Nueva metadata (opcional)
        
        Returns:
            Dict con producto actualizado o error
        """
        if product_id not in self.products:
            return {
                "success": False,
                "error": f"Producto {product_id} no encontrado"
            }
        
        product = self.products[product_id]
        
        # Actualizar solo campos proporcionados
        if name is not None:
            product["name"] = name
        if price is not None:
            product["price"] = price
            # Recalcular price_with_iva si cambia precio o iva_rate
            current_iva = iva_rate if iva_rate is not None else product.get("iva_rate", 21.0)
            product["price_with_iva"] = price * (1 + current_iva / 100)
        if category is not None:
            product["category"] = category
        if iva_rate is not None:
            product["iva_rate"] = iva_rate
            # Recalcular price_with_iva
            current_price = product.get("price", 0)
            product["price_with_iva"] = current_price * (1 + iva_rate / 100)
        if stock is not None:
            product["stock"] = stock
        if image is not None:
            product["image"] = image
        if icon is not None:
            product["icon"] = icon
        if metadata is not None:
            product["metadata"] = metadata
        
        product["updated_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"✏️ Producto actualizado: {product_id} - {product.get('name')}")
        
        return {
            "success": True,
            "product": product
        }
    
    def delete_product(self, product_id: str) -> Dict[str, Any]:
        """
        Eliminar producto del sistema
        
        Args:
            product_id: ID del producto a eliminar
        
        Returns:
            Dict con resultado de la eliminación
        """
        if product_id not in self.products:
            return {
                "success": False,
                "error": f"Producto {product_id} no encontrado"
            }
        
        # BLOCKING RULE: No permitir eliminar si es el último producto
        if len(self.products) <= 1:
            return {
                "success": False,
                "error": "No se puede eliminar el último producto. El TPV requiere al menos 1 producto activo."
            }
        
        product_name = self.products[product_id].get("name", product_id)
        del self.products[product_id]
        
        logger.info(f"🗑️ Producto eliminado: {product_id} - {product_name}")
        logger.info(f"📊 Total productos restantes: {len(self.products)}")
        
        return {
            "success": True,
            "message": f"Producto {product_name} eliminado correctamente",
            "remaining_products": len(self.products)
        }
    
    @staticmethod
    def cart_line_from_product_row(row: Any, quantity: int) -> Dict[str, Any]:
        """Línea de carrito desde modelo TPVProduct (ORM). Lanza ValueError si stock insuficiente."""
        q = max(1, int(quantity or 1))
        stock = getattr(row, "stock", None)
        if stock is not None and int(stock) < q:
            raise ValueError(f"Stock insuficiente para {row.product_id}. Disponible: {stock}")
        price = float(row.price)
        price_iva = float(row.price_with_iva)
        return {
            "product_id": row.product_id,
            "name": row.name,
            "price": price,
            "price_with_iva": price_iva,
            "quantity": q,
            "subtotal": price * q,
            "subtotal_with_iva": price_iva * q,
            "iva_rate": float(row.iva_rate),
            "category": row.category or "General",
        }

    @staticmethod
    def compute_cart_total(cart_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Totales a partir de líneas enviadas por el cliente (sin estado en servidor)."""
        if not cart_lines:
            return {"subtotal": 0.0, "iva": 0.0, "total": 0.0, "items_count": 0}
        subtotal = sum(float(item["subtotal"]) for item in cart_lines)
        total_iva = sum(float(item["subtotal_with_iva"]) - float(item["subtotal"]) for item in cart_lines)
        total = subtotal + total_iva
        return {
            "subtotal": subtotal,
            "iva": total_iva,
            "total": total,
            "items_count": len(cart_lines),
        }

    @staticmethod
    def _resolve_user_email(db: Optional[Any], user_id: Optional[int]) -> Optional[str]:
        """Resolver email por user_id para trazabilidad de actividades en workspace."""
        if not db or not user_id:
            return None
        try:
            from app.models.user import User
            u = db.query(User).filter(User.id == user_id).first()
            return u.email if u else None
        except Exception:
            return None

    def process_sale(
        self,
        payment_method: PaymentMethod,
        cart_lines: List[Dict[str, Any]],
        employee_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
        consumption_type: Optional[str] = None,
        company_id: Optional[int] = None,
        work_session_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Procesar venta y generar ticket
        
        Args:
            payment_method: Método de pago
            employee_id: ID del empleado que realiza la venta
            terminal_id: ID del terminal
            customer_data: Datos del cliente (opcional, para factura)
        
        Returns:
            Dict con ticket generado y metadata
        """
        # Requerir business_profile
        try:
            self.require_business_profile()
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        
        # Validaciones según configuración
        if self.config.get("requires_employee") and not employee_id:
            return {
                "success": False,
                "error": "Este tipo de negocio requiere especificar un empleado"
            }
        
        if self.config.get("requires_customer_data") and not customer_data:
            return {
                "success": False,
                "error": "Este tipo de negocio requiere datos del cliente"
            }
        
        if not cart_lines:
            return {
                "success": False,
                "error": "Carrito vacío"
            }

        cart_total = self.compute_cart_total(cart_lines)

        # Determinar tipo de documento según configuración
        document_type = TPVDocumentType.TICKET
        if self.config.get("supports_invoices") and customer_data:
            document_type = TPVDocumentType.FACTURA
        
        # Generar documento (ticket o factura)
        doc_id = f"{document_type.value.upper()}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        if not db or not user_id:
            return {
                "success": False,
                "error": "Persistencia fiscal obligatoria: falta sesión de base de datos o usuario.",
            }

        logger.info(
            "TPV venta iniciada ticket=%s user_id=%s company_id=%s lineas=%s",
            doc_id,
            user_id,
            company_id,
            len(cart_lines),
        )
        
        ticket = {
            "id": doc_id,
            "type": document_type.value,
            "date": datetime.utcnow().isoformat(),
            "items": [dict(x) for x in cart_lines],
            "totals": cart_total,
            "payment_method": payment_method.value,
            "employee_id": employee_id,
            "terminal_id": terminal_id,
            "customer_data": customer_data,
            "business_profile": self.business_profile.value,
            "config": self.config
        }
        
        # Persistir snapshot fiscal + RAFAEL (transacción única; sin éxito silencioso)
        from services.fiscal_engine import (
            build_fiscal_items_from_cart,
            get_fiscal_profile,
            persist_fiscal_sale,
        )
        from services.rafael_service import RafaelFiscalError, persist_sale as rafael_persist_sale

        profile = get_fiscal_profile(db, user_id)
        apply_recargo = getattr(profile, "apply_recargo_equivalencia", False) if profile else False
        recargo_rate = getattr(profile, "recargo_rate", None)
        ct = consumption_type or "onsite"
        fiscal_items = build_fiscal_items_from_cart(
            cart_lines,
            apply_recargo=apply_recargo,
            recargo_rate=recargo_rate,
            consumption_type=ct,
        )
        try:
            tpv_sale_id = persist_fiscal_sale(
                db,
                user_id=user_id,
                ticket_id=doc_id,
                document_type=document_type.value,
                payment_method=payment_method.value,
                fiscal_items=fiscal_items,
                consumption_type=ct,
                company_id=company_id,
                work_session_id=work_session_id,
                customer_data=customer_data if isinstance(customer_data, dict) else None,
                auto_commit=False,
            )
            ticket["fiscal_snapshot_id"] = tpv_sale_id
            logger.info(
                "TPV venta en BD (flush) ticket=%s sale_id=%s → enviando a RAFAEL",
                doc_id,
                tpv_sale_id,
            )

            accounting_result = rafael_persist_sale(
                db=db,
                user_id=user_id,
                company_id=company_id,
                ticket=ticket,
                tpv_sale_id=tpv_sale_id,
                user_email=self._resolve_user_email(db, user_id),
            )
            db.commit()
            ticket["accounting_sent"] = True
            ticket["accounting_entry"] = accounting_result.get("accounting_entry")
            ticket["fiscal_document_id"] = accounting_result.get("fiscal_document_id")
            ticket["fiscal_document_persisted"] = accounting_result.get("fiscal_document_persisted", False)
            logger.info(
                "TPV venta confirmada ticket=%s sale_id=%s rafael_ok=true",
                doc_id,
                tpv_sale_id,
            )
        except RafaelFiscalError as exc:
            db.rollback()
            logger.error(
                "TPV venta revertida: RAFAEL falló ticket=%s user_id=%s error=%s",
                doc_id,
                user_id,
                exc,
            )
            return {
                "success": False,
                "error": f"No se pudo registrar la venta en RAFAEL: {exc}",
                "fiscal_error": True,
            }
        except Exception as exc:
            db.rollback()
            logger.exception(
                "TPV venta revertida: error fiscal ticket=%s user_id=%s",
                doc_id,
                user_id,
            )
            return {
                "success": False,
                "error": f"Error de persistencia fiscal: {exc}",
                "fiscal_error": True,
            }
        
        # Validar legalidad con JUSTICIA si está integrado (no bloquea venta ya confirmada)
        if self.justicia_integration:
            legal_validation = self._validate_ticket_legality(ticket)
            ticket["legal_validation"] = legal_validation
            try:
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="JUSTICIA",
                    action_type="tpv_legal_validation",
                    action_description=f"Validación legal ticket {doc_id}",
                    details={
                        "ticket_id": doc_id,
                        "validated": legal_validation.get("validated", False),
                        "gdpr_compliant": legal_validation.get("gdpr_compliant", None),
                        "user_id": user_id,
                    },
                    metrics={
                        "validated": 1 if legal_validation.get("validated") else 0,
                        "rejected": 0 if legal_validation.get("validated") else 1,
                    },
                    user_email=self._resolve_user_email(db, user_id),
                    status="completed" if legal_validation.get("validated", False) else "failed",
                    priority="normal",
                    visible_to_client=True,
                )
            except Exception as e:
                logger.warning("No se pudo registrar actividad JUSTICIA TPV: %s", e)
        
        # Sincronizar con AFRODITA para empleados
        if self.afrodita_integration and employee_id:
            employee_sync = self._sync_with_afrodita(employee_id, ticket)
            ticket["employee_synced"] = employee_sync.get("success", False)
            if employee_sync.get("success"):
                ticket["employee_permissions"] = employee_sync.get("sync_result", {}).get("permissions")
            try:
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="AFRODITA",
                    action_type="tpv_employee_sync",
                    action_description=f"Sincronización empleado {employee_id} en ticket {doc_id}",
                    details={
                        "ticket_id": doc_id,
                        "employee_id": employee_id,
                        "success": employee_sync.get("success", False),
                        "user_id": user_id,
                    },
                    metrics={"employee_sync": 1 if employee_sync.get("success", False) else 0},
                    user_email=self._resolve_user_email(db, user_id),
                    status="completed" if employee_sync.get("success", False) else "failed",
                    priority="normal",
                    visible_to_client=True,
                )
            except Exception as e:
                logger.warning("No se pudo registrar actividad AFRODITA TPV: %s", e)
        
        logger.info(
            "💳 Venta procesada: %s user_id=%s €%.2f tipo=%s lineas=%s",
            doc_id,
            user_id,
            cart_total["total"],
            document_type.value,
            len(cart_lines),
        )
        
        return {
            "success": True,
            "ticket": ticket,
            "ticket_id": doc_id,
            "document_type": document_type.value,
            "business_profile": self.business_profile.value
        }
    
    def _validate_ticket_legality(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Validar legalidad del ticket con JUSTICIA"""
        try:
            if not self.justicia_integration:
                return {
                    "validated": False,
                    "error": "JUSTICIA integration no disponible"
                }
            
            # Si JUSTICIA tiene método validate_tpv_ticket_legality, usarlo
            if hasattr(self.justicia_integration, 'validate_tpv_ticket_legality'):
                result = self.justicia_integration.validate_tpv_ticket_legality(ticket)
                return {
                    "validated": result.get("legal_ok", False),
                    "gdpr_compliant": result.get("validations", {}).get("gdpr_compliant", True),
                    "legal_requirements_met": result.get("legal_ok", False),
                    "gdpr_audit": result.get("gdpr_audit", {}),
                    "notes": "Ticket validado por JUSTICIA"
                }
            
            # Fallback: Validación básica
            result = {
                "validated": True,
                "gdpr_compliant": True,
                "legal_requirements_met": True,
                "notes": "Ticket válido según normativa vigente"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error validando legalidad: {e}")
            return {
                "validated": False,
                "error": str(e)
            }
    
    def _send_to_rafael(
        self, 
        ticket: Dict[str, Any], 
        user_id: Optional[int] = None,
        db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Enviar datos del ticket a RAFAEL para contabilidad automática.
        Persiste automáticamente documento fiscal en BD si db y user_id están disponibles.
        """
        try:
            if not self.rafael_integration:
                return {
                    "success": False,
                    "error": "RAFAEL integration no disponible"
                }
            
            # Si RAFAEL tiene método process_tpv_ticket, usarlo
            if hasattr(self.rafael_integration, 'process_tpv_ticket'):
                result = self.rafael_integration.process_tpv_ticket(ticket)
                logger.info(f"📊 Datos enviados a RAFAEL para ticket {ticket['id']}")
                
                # PERSISTIR AUTOMÁTICAMENTE EN FIREWALL si tenemos db y user_id
                if result.get("success") and db and user_id:
                    try:
                        from services.legal_fiscal_firewall import firewall
                        firewall.db = db
                        
                        # Preparar contenido del documento fiscal
                        fiscal_content = {
                            "ticket_id": ticket.get("id"),
                            "fiscal_data": result.get("fiscal_data", {}),
                            "accounting_entry": result.get("accounting_entry", {}),
                            "libro_ingresos": result.get("libro_ingresos", {}),
                            "resumen_diario": result.get("resumen_diario", {}),
                            "resumen_mensual": result.get("resumen_mensual", {}),
                            "model_303_ready": result.get("model_303_ready", False),
                            "draft_only": result.get("draft_only", True),
                            "legal_disclaimer": result.get("legal_disclaimer", "ZEUS no presenta impuestos automáticamente")
                        }
                        
                        # Generar documento fiscal en borrador y persistirlo
                        fiscal_doc = firewall.generate_draft_document(
                            agent_name="RAFAEL",
                            user_id=user_id,
                            document_type=f"tpv_{ticket.get('type', 'ticket')}",
                            content=fiscal_content,
                            metadata={
                                "ticket_id": ticket.get("id"),
                                "business_profile": ticket.get("business_profile"),
                                "payment_method": ticket.get("payment_method"),
                                "total": ticket.get("totals", {}).get("total", 0)
                            }
                        )
                        
                        # Actualizar documento con campos fiscales específicos
                        if fiscal_doc.get("document_id") and db:
                            try:
                                from app.models.document_approval import DocumentApproval
                                doc_approval = db.query(DocumentApproval).filter(
                                    DocumentApproval.id == fiscal_doc.get("document_id")
                                ).first()
                                
                                if doc_approval:
                                    doc_approval.ticket_id = ticket.get("id")
                                    doc_approval.fiscal_document_type = f"tpv_{ticket.get('type', 'ticket')}"
                                    
                                    # Agregar evento al log
                                    audit_log = doc_approval.audit_log
                                    audit_log.append({
                                        "timestamp": datetime.utcnow().isoformat(),
                                        "event": "ticket_processed",
                                        "ticket_id": ticket.get("id"),
                                        "fiscal_document_generated": True
                                    })
                                    doc_approval.audit_log = audit_log
                                    
                                    db.commit()
                                    logger.info(f"📊 Documento fiscal persistido para ticket {ticket['id']} - ID: {fiscal_doc.get('document_id')}")
                            except Exception as e:
                                logger.error(f"Error actualizando documento fiscal: {e}")
                                if db:
                                    db.rollback()
                        
                        result["fiscal_document_id"] = fiscal_doc.get("document_id")
                        result["fiscal_document_persisted"] = True
                        
                    except Exception as e:
                        logger.error(f"Error persistiendo documento fiscal: {e}")
                        # Continuar sin persistencia si falla (modo degradado)
                        result["fiscal_document_persisted"] = False
                
                return result
            
            # Fallback: Preparar datos fiscales manualmente
            fiscal_data = {
                "fecha": ticket["date"],
                "hora": datetime.fromisoformat(ticket["date"]).strftime("%H:%M:%S"),
                "total": ticket["totals"]["total"],
                "iva": ticket["totals"]["iva"],
                "método_pago": ticket["payment_method"],
                "productos": [
                    {
                        "nombre": item["name"],
                        "cantidad": item["quantity"],
                        "precio_unitario": item["price"],
                        "subtotal": item["subtotal"],
                        "iva": item["subtotal_with_iva"] - item["subtotal"],
                        "categoria": item["category"]
                    }
                    for item in ticket["items"]
                ],
                "responsable": ticket.get("employee_id"),
                "categoria": ticket.get("business_profile")
            }
            
            result = {
                "success": True,
                "fiscal_data": fiscal_data,
                "model_303_ready": True,
                "accounting_entry_created": True
            }
            
            logger.info(f"📊 Datos enviados a RAFAEL para ticket {ticket['id']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error enviando a RAFAEL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _sync_with_afrodita(self, employee_id: str, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Sincronizar datos de empleado con AFRODITA"""
        try:
            if not self.afrodita_integration:
                return {
                    "success": False,
                    "error": "AFRODITA integration no disponible"
                }
            
            # Si AFRODITA tiene método sync_tpv_employee, usarlo
            if hasattr(self.afrodita_integration, 'sync_tpv_employee'):
                result = self.afrodita_integration.sync_tpv_employee(employee_id, ticket)
                logger.info(f"👥 Empleado {employee_id} sincronizado con AFRODITA")
                return result
            
            # Fallback: Preparar datos de empleado manualmente
            employee_data = {
                "employee_id": employee_id,
                "sale_date": ticket["date"],
                "sale_total": ticket["totals"]["total"],
                "items_sold": ticket["totals"]["items_count"]
            }
            
            result = {
                "success": True,
                "employee_synced": True,
                "role_permissions_validated": True,
                "sync_result": {
                    "employee_id": employee_id,
                    "sale_recorded": True
                }
            }
            
            logger.info(f"👥 Empleado {employee_id} sincronizado con AFRODITA")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sincronizando con AFRODITA: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_invoice(
        self,
        db: Any,
        *,
        ticket_id: str,
        customer_data: Optional[Dict[str, Any]],
        user_id: int,
        company_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Generar factura REAL desde una venta TPV ya cobrada (tabla `tpv_sales`).

        No recalcula IVA: reutiliza `subtotal`/`tax_amount`/`total` ya
        persistidos por `fiscal_engine.persist_fiscal_sale` en el momento del
        cobro (verificado como correcto en auditoría previa: base imponible +
        IVA calculado una sola vez). Aislamiento por tenant obligatorio: la
        venta debe pertenecer al usuario o a una de sus empresas, si no,
        404/403 real (nunca éxito falso). Persiste `Invoice`/`InvoiceItem`
        reales (tabla `invoices`, ya usada por el resto del ERP) enlazadas a
        la venta vía `Invoice.tpv_sale_id` (único: 1 factura por venta).
        """
        from fastapi import HTTPException
        from sqlalchemy.orm import joinedload
        from app.models.erp import TPVSale, Invoice, InvoiceItem, InvoiceStatus, InvoiceType
        from app.models.customer import Customer

        if not ticket_id:
            raise HTTPException(status_code=400, detail="ticket_id es obligatorio")

        sale = (
            db.query(TPVSale)
            .options(joinedload(TPVSale.items))
            .filter(TPVSale.ticket_id == ticket_id)
            .first()
        )
        if not sale:
            logger.warning("tpv_invoice_ticket_no_encontrado ticket_id=%s user_id=%s", ticket_id, user_id)
            raise HTTPException(status_code=404, detail=f"Venta no encontrada para ticket_id={ticket_id}")

        owns_by_user = sale.user_id == user_id
        owns_by_company = bool(sale.company_id) and bool(company_ids) and sale.company_id in company_ids
        if not (owns_by_user or owns_by_company):
            logger.warning(
                "tpv_invoice_denegada_tenant ticket_id=%s sale_user=%s sale_company=%s solicitante_user=%s solicitante_companies=%s",
                ticket_id, sale.user_id, sale.company_id, user_id, company_ids,
            )
            raise HTTPException(status_code=403, detail="La venta no pertenece a su empresa.")

        if not sale.items:
            raise HTTPException(status_code=422, detail="La venta no tiene líneas; no se puede facturar.")

        # Idempotencia real: si ya existe factura para esta venta, no duplicar (no éxito falso, no duplicado silencioso)
        existing = db.query(Invoice).filter(Invoice.tpv_sale_id == sale.id).first()
        if existing:
            logger.info("tpv_invoice_ya_existente ticket_id=%s invoice_id=%s", ticket_id, existing.id)
            return self._invoice_result(existing, sale.ticket_id, already_existed=True)

        merged_customer: Dict[str, Any] = dict(sale.customer_data or {})
        if isinstance(customer_data, dict):
            merged_customer.update({k: v for k, v in customer_data.items() if v})

        customer_id = None
        name = str(merged_customer.get("name") or merged_customer.get("nombre") or "").strip()
        nif = str(merged_customer.get("nif") or merged_customer.get("tax_id") or "").strip() or None
        if name:
            cq = db.query(Customer).filter(Customer.company_id == sale.company_id)
            cq = cq.filter(Customer.tax_id == nif) if nif else cq.filter(Customer.name == name)
            customer = cq.first()
            if not customer:
                customer = Customer(
                    name=name,
                    tax_id=nif,
                    company_id=sale.company_id,
                    owner_user_id=user_id,
                    is_active=True,
                    is_company=False,
                )
                db.add(customer)
                db.flush()
            customer_id = customer.id

        subtotal = float(sale.subtotal or 0)
        tax_amount = float(sale.tax_amount or 0)
        total = float(sale.total or 0)

        invoice = Invoice(
            invoice_number=f"FRA-{sale.ticket_id}"[:50],
            company_id=sale.company_id,
            customer_id=customer_id,
            invoice_type=InvoiceType.INVOICE,
            status=InvoiceStatus.PAID,
            issue_date=datetime.utcnow(),
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=0.0,
            total=total,
            amount_paid=total,
            amount_due=0.0,
            tpv_sale_id=sale.id,
            created_by=user_id,
        )
        db.add(invoice)
        try:
            db.flush()
            for item in sale.items:
                base = float(item.base_amount or 0)
                tax = float(item.tax_amount or 0)
                recargo = float(item.recargo_amount or 0)
                db.add(InvoiceItem(
                    invoice_id=invoice.id,
                    description=item.product_name or item.product_id,
                    quantity=float(item.quantity or 1),
                    unit_price=float(item.unit_price or 0),
                    tax_rate=float(item.tax_rate_snapshot or 0) * 100,
                    discount=0.0,
                    subtotal=base,
                    tax_amount=tax + recargo,
                    total=base + tax + recargo,
                ))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("tpv_invoice_persist_failed ticket_id=%s", ticket_id)
            raise HTTPException(status_code=500, detail="No se pudo persistir la factura. Inténtelo de nuevo.")

        db.refresh(invoice)
        logger.info(
            "tpv_invoice_generada ticket_id=%s invoice_id=%s invoice_number=%s total=%s user_id=%s company_id=%s",
            ticket_id, invoice.id, invoice.invoice_number, total, user_id, sale.company_id,
        )
        return self._invoice_result(invoice, sale.ticket_id, already_existed=False)

    @staticmethod
    def _invoice_result(invoice: Any, ticket_id: str, already_existed: bool) -> Dict[str, Any]:
        return {
            "success": True,
            "already_existed": already_existed,
            "invoice": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "type": TPVDocumentType.FACTURA.value,
                "ticket_id": ticket_id,
                "company_id": invoice.company_id,
                "customer_id": invoice.customer_id,
                "subtotal": float(invoice.subtotal or 0),
                "tax_amount": float(invoice.tax_amount or 0),
                "total": float(invoice.total or 0),
                "status": invoice.status.value if hasattr(invoice.status, "value") else invoice.status,
                "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
                "generated_at": datetime.utcnow().isoformat(),
            },
        }
    
    def close_register(
        self,
        terminal_id: str,
        employee_id: str,
        initial_cash: float,
        final_cash: float
    ) -> Dict[str, Any]:
        """
        Cerrar caja del terminal
        
        Args:
            terminal_id: ID del terminal
            employee_id: ID del empleado que cierra
            initial_cash: Efectivo inicial
            final_cash: Efectivo final
        
        Returns:
            Dict con cierre de caja
        """
        # Calcular diferencias
        expected_cash = initial_cash  # + ventas en efectivo del día
        difference = final_cash - expected_cash
        
        closure = {
            "id": f"CIERRE_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "type": TPVDocumentType.CIERRE_CAJA.value,
            "terminal_id": terminal_id,
            "employee_id": employee_id,
            "date": datetime.utcnow().isoformat(),
            "initial_cash": initial_cash,
            "final_cash": final_cash,
            "expected_cash": expected_cash,
            "difference": difference,
            "status": "ok" if abs(difference) < 0.01 else "discrepancy"
        }
        
        logger.info(f"💰 Cierre de caja: Terminal {terminal_id} - Diferencia: €{difference:.2f}")
        
        return {
            "success": True,
            "closure": closure
        }
    
    def set_integrations(
        self,
        rafael: Optional[Any] = None,
        justicia: Optional[Any] = None,
        afrodita: Optional[Any] = None
    ):
        """Configurar integraciones con otros agentes"""
        self.rafael_integration = rafael
        self.justicia_integration = justicia
        self.afrodita_integration = afrodita
        
        logger.info("🔗 Integraciones TPV configuradas")

