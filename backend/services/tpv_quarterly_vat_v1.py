"""IVA trimestral de las ventas TPV (bases y cuotas por tipo 4/10/21 % y recargo).

Es el calculo de `GET /api/v1/tpv/fiscal/quarterly-vat` extraido tal cual del endpoint para que lo
reutilicen el endpoint y la consulta del chat de RAFAEL (`get_vat_quarter`) sin duplicarlo. Solo
lectura: suma los snapshots fiscales inmutables de cada linea de venta; no envia nada a la AEAT.

El AMBITO (que ventas entran) lo decide quien llama con `scope_filter`: el endpoint usa las empresas
del usuario (+ ventas legado sin empresa del propio usuario); el chat, solo la empresa de la sesion.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session


def quarter_bounds(year: int, quarter: int) -> Tuple[datetime, datetime]:
    """[inicio, fin) del trimestre, igual que el endpoint (inicio de dia, sin zona)."""
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3
    start_d = date(year, start_month, 1)
    if end_month == 12:
        end_d = date(year + 1, 1, 1)
    else:
        end_d = date(year, end_month + 1, 1)
    # Comparar con inicio/fin de día para DateTime(timezone=True)
    return datetime.combine(start_d, datetime.min.time()), datetime.combine(end_d, datetime.min.time())


def quarterly_vat_breakdown(
    db: Session, scope_filter: Any, year: int, quarter: int, *, include_sales_count: bool = False
) -> Dict[str, Any]:
    from app.models.fiscal import TPVSale

    start_ts, end_ts = quarter_bounds(year, quarter)
    sales = (
        db.query(TPVSale)
        .filter(
            scope_filter,
            TPVSale.sale_date >= start_ts,
            TPVSale.sale_date < end_ts,
        )
        .all()
    )
    base_4 = base_10 = base_21 = iva_4 = iva_10 = iva_21 = recargo_total = grand_total = 0.0
    for s in sales:
        for item in s.items:
            rate_pct = float(item.tax_rate_snapshot or 0) * 100
            base = float(item.base_amount or 0)
            iva = float(item.tax_amount or 0)
            if rate_pct <= 5:
                base_4 += base
                iva_4 += iva
            elif rate_pct <= 15:
                base_10 += base
                iva_10 += iva
            else:
                base_21 += base
                iva_21 += iva
            recargo_total += float(item.recargo_amount or 0)
        grand_total += float(s.total or 0)
    out: Dict[str, Any] = {
        "period": f"{year}-Q{quarter}",
        "base_4": round(base_4, 2),
        "iva_4": round(iva_4, 2),
        "base_10": round(base_10, 2),
        "iva_10": round(iva_10, 2),
        "base_21": round(base_21, 2),
        "iva_21": round(iva_21, 2),
        "recargo_total": round(recargo_total, 2),
        "grand_total": round(grand_total, 2),
        "modelo_303_ready": True,
    }
    if include_sales_count:
        # Solo el chat (no cambia la respuesta del endpoint): distingue «0 €» de «sin ventas».
        out["sales_count"] = len(sales)
    return out
