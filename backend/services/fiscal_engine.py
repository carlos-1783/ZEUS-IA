"""
ZEUS_TPV_FULL_FISCAL_INFRASTRUCTURE_ES_003
Motor fiscal España: multi-IVA, recargo equivalencia, consumo local/para llevar.
Backend = única fuente de verdad; snapshot inmutable por línea.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_fiscal_profile(db: Any, user_id: int) -> Optional[Any]:
    """Obtener perfil fiscal del usuario (régimen IVA, recargo equivalencia)."""
    try:
        from app.models.erp import FiscalProfile
        profile = db.query(FiscalProfile).filter(FiscalProfile.user_id == user_id).first()
        return profile
    except Exception as e:
        logger.debug(f"FiscalProfile not found for user {user_id}: {e}")
        return None


def _decimal(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(float(val) if val is not None else 0))


def build_fiscal_items_from_cart(
    cart: List[Dict[str, Any]],
    apply_recargo: bool = False,
    recargo_rate: Optional[float] = None,
    consumption_type: str = "onsite",
) -> List[Dict[str, Any]]:
    """
    Construir líneas fiscales desde el carrito.
    base_amount = price * quantity (precio unitario sin IVA).
    tax_amount = base_amount * tax_rate.
    recargo_amount = base_amount * recargo_rate si apply_recargo.
    """
    recargo = _decimal(recargo_rate or 0)
    items = []
    for item in cart:
        price = _decimal(item.get("price", 0))
        qty = _decimal(item.get("quantity", 1))
        tax_rate = _decimal(item.get("iva_rate", 21)) / 100  # 21 -> 0.21
        base_amount = (price * qty).quantize(Decimal("0.01"))
        tax_amount = (base_amount * tax_rate).quantize(Decimal("0.01"))
        recargo_amount = Decimal("0")
        recargo_snapshot = None
        if apply_recargo and recargo:
            recargo_amount = (base_amount * recargo).quantize(Decimal("0.01"))
            recargo_snapshot = recargo
        items.append({
            "product_id": str(item.get("product_id", "")),
            "product_name": str(item.get("name", "")),
            "quantity": qty,
            "unit_price": price,
            "tax_rate_snapshot": tax_rate,
            "tax_amount": tax_amount,
            "base_amount": base_amount,
            "recargo_rate_snapshot": recargo_snapshot,
            "recargo_amount": recargo_amount,
            "consumption_type": consumption_type,
        })
    return items


def persist_fiscal_sale(
    db: Any,
    user_id: int,
    ticket_id: str,
    document_type: str,
    payment_method: str,
    fiscal_items: List[Dict[str, Any]],
    consumption_type: Optional[str] = None,
) -> Optional[int]:
    """
    Persistir venta fiscal en tpv_sales y tpv_sale_items (snapshot inmutable).
    Retorna tpv_sale.id o None si falla.
    """
    try:
        from app.models.erp import TPVSale, TPVSaleItem
        subtotal = sum(_decimal(i["base_amount"]) for i in fiscal_items)
        tax_total = sum(_decimal(i["tax_amount"]) for i in fiscal_items)
        recargo_total = sum(_decimal(i.get("recargo_amount") or 0) for i in fiscal_items)
        total = subtotal + tax_total + recargo_total
        sale = TPVSale(
            user_id=user_id,
            ticket_id=ticket_id,
            document_type=document_type,
            payment_method=payment_method,
            consumption_type=consumption_type or "onsite",
            subtotal=subtotal,
            tax_amount=tax_total,
            recargo_amount=recargo_total if recargo_total else None,
            total=total,
        )
        db.add(sale)
        db.flush()
        for row in fiscal_items:
            line = TPVSaleItem(
                tpv_sale_id=sale.id,
                product_id=row["product_id"],
                product_name=row["product_name"],
                quantity=row["quantity"],
                unit_price=row["unit_price"],
                tax_rate_snapshot=row["tax_rate_snapshot"],
                tax_amount=row["tax_amount"],
                base_amount=row["base_amount"],
                recargo_rate_snapshot=row.get("recargo_rate_snapshot"),
                recargo_amount=row.get("recargo_amount") or 0,
                consumption_type=row.get("consumption_type"),
            )
            db.add(line)
        db.commit()
        logger.info(f"Fiscal sale persisted: ticket_id={ticket_id} tpv_sale_id={sale.id}")
        return sale.id
    except Exception as e:
        logger.exception(f"persist_fiscal_sale failed: {e}")
        db.rollback()
        return None
