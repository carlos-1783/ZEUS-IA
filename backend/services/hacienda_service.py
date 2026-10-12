"""
Hacienda (AEAT): SII y Modelo 303.

Fase 2 / Step 2 (sin simulacion): antes, con AEAT_ENVIRONMENT=test (el valor por defecto),
`enviar_factura_emitida` devolvia success=True, estado "Aceptada (SIMULADO)" y un CSV fijo
("TEST-CSV-123456789"), y el Modelo 303 un CSV inventado: el cliente creia haber presentado
ante Hacienda algo que nunca salio del servidor. Habia ademas un `generar_factura_pdf` que
devolvia una URL a un PDF inexistente (sin usos: eliminado).

Ahora:
- Sin credenciales -> 503 con las variables que faltan.
- Con credenciales -> 501: no existe cliente SOAP firmado con certificado (SII / presentacion
  telematica). Nunca se devuelve un CSV ni un estado de aceptacion.
- El calculo del Modelo 303 (repercutido - soportado) si es real: se devuelve como borrador
  explicitamente NO presentado, dentro del error, para que el usuario pueda revisarlo.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_REQUIRED_ENV = ["AEAT_NIF", "AEAT_PASSWORD", "AEAT_CERTIFICATE_PATH"]
_MISSING_CLIENT = (
    "no hay cliente SOAP de la AEAT firmado con certificado digital "
    "(SII / presentacion telematica) integrado en ZEUS"
)


class HaciendaError(Exception):
    """Error con codigo HTTP y detalle estructurado, sin exito fingido."""

    def __init__(self, status_code: int, detail: Dict[str, Any]):
        super().__init__(detail.get("message") or detail.get("error"))
        self.status_code = status_code
        self.detail = detail


class HaciendaService:
    def __init__(self) -> None:
        self.environment = os.getenv("AEAT_ENVIRONMENT", "test")

    @staticmethod
    def missing_config() -> List[str]:
        return [k for k in _REQUIRED_ENV if not os.getenv(k)]

    def is_configured(self) -> bool:
        return not self.missing_config()

    def _unavailable(self, what: str, extra: Dict[str, Any] | None = None) -> HaciendaError:
        missing = self.missing_config()
        if missing:
            detail = {"error": "aeat_not_configured", "missing": missing,
                      "message": f"{what}: no se ha enviado nada a la AEAT (faltan credenciales)."}
            code = 503
        else:
            detail = {"error": "aeat_not_implemented",
                      "message": f"{what} no esta implementado: {_MISSING_CLIENT}. No se ha enviado nada."}
            code = 501
        detail.update(extra or {})
        logger.warning("Hacienda: %s rechazado (%s)", what, detail["error"])
        return HaciendaError(code, detail)

    async def enviar_factura_emitida(self, factura_data: Dict[str, Any]) -> Dict[str, Any]:
        raise self._unavailable(
            "Enviar la factura al SII", {"factura_numero": factura_data.get("numero"), "enviada": False}
        )

    @staticmethod
    def calcular_modelo_303(trimestre: int, ejercicio: int, datos: Dict[str, Any]) -> Dict[str, Any]:
        repercutido = float(datos.get("cuota_iva_repercutido") or 0)
        soportado = float(datos.get("cuota_iva_soportado") or 0)
        resultado = round(repercutido - soportado, 2)
        return {
            "modelo": "303",
            "periodo": f"{trimestre}T/{ejercicio}",
            "base_imponible": float(datos.get("base_imponible_general") or 0),
            "iva_repercutido": repercutido,
            "iva_soportado": soportado,
            "resultado": resultado,
            "tipo": "A ingresar" if resultado > 0 else ("A devolver/compensar" if resultado < 0 else "Sin actividad"),
            "presentado": False,
        }

    async def presentar_modelo_303(self, trimestre: int, ejercicio: int, datos: Dict[str, Any]) -> Dict[str, Any]:
        borrador = self.calcular_modelo_303(trimestre, ejercicio, datos)
        raise self._unavailable("Presentar el Modelo 303", {"borrador_no_presentado": borrador})

    def get_status(self) -> Dict[str, Any]:
        nif = os.getenv("AEAT_NIF")
        return {
            "configured": self.is_configured(),
            "missing": self.missing_config(),
            "environment": self.environment,
            "nif": nif[:3] + "****" + nif[-2:] if nif else None,
            "sii_implemented": False,
            "presentacion_implemented": False,
            "modelos_disponibles": [],
            "calculo_303_borrador": True,
        }


hacienda_service = HaciendaService()
