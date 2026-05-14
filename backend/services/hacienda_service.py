"""
📊 Hacienda Service - AEAT Integration
Automatiza facturación y presentación de modelos fiscales
"""
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

try:
    import zeep  # pyright: ignore[reportMissingImports]
    from zeep import Client as SoapClient  # pyright: ignore[reportMissingImports]
    from zeep.wsse.username import UsernameToken  # pyright: ignore[reportMissingImports]
    import xmltodict  # pyright: ignore[reportMissingImports, reportMissingModuleSource]
    ZEEP_AVAILABLE = True
except ImportError:
    ZEEP_AVAILABLE = False
    zeep = SoapClient = UsernameToken = xmltodict = None

class HaciendaService:
    """Servicio para integración con Hacienda (AEAT)"""
    
    def __init__(self):
        self.nif = os.getenv("AEAT_NIF")
        self.password = os.getenv("AEAT_PASSWORD")
        self.environment = os.getenv("AEAT_ENVIRONMENT", "test")  # test o production
        
        # URLs de Hacienda
        self.sii_urls = {
            "test": "https://www7.aeat.es/wlpl/TIKE-CONT/SuministroInformacion",
            "production": "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/SuministroInformacion"
        }
        
        self.client = None
        if not ZEEP_AVAILABLE:
            logger.warning("Hacienda Service: SOAP libraries not installed (pip install zeep xmltodict)")
        elif self.nif and self.password:
            logger.info("Hacienda Service: configured (mode=%s)", self.environment)
        else:
            logger.warning("Hacienda Service: AEAT credentials not configured")
    
    def is_configured(self) -> bool:
        """Verificar si el servicio está configurado"""
        return bool(self.nif and self.password)
    
    async def enviar_factura_emitida(
        self,
        factura_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enviar factura emitida al SII (Suministro Inmediato de Información)
        
        Args:
            factura_data: Datos de la factura
                - numero: Número de factura
                - fecha: Fecha de emisión (YYYY-MM-DD)
                - cliente_nif: NIF del cliente
                - cliente_nombre: Nombre del cliente
                - base_imponible: Base imponible
                - tipo_iva: Tipo de IVA (21, 10, 4)
                - cuota_iva: Cuota de IVA
                - total: Total factura
                
        Returns:
            Dict con resultado del envío
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Hacienda service not configured. Set AEAT_NIF and AEAT_PASSWORD"
            }
        
        try:
            # Construir XML para SII
            periodo = {
                "Ejercicio": factura_data["fecha"][:4],
                "Periodo": factura_data["fecha"][5:7]
            }
            
            factura_xml = {
                "IDFactura": {
                    "NumSerieFactura": factura_data["numero"],
                    "FechaExpedicionFactura": factura_data["fecha"]
                },
                "Contraparte": {
                    "NIF": factura_data["cliente_nif"],
                    "NombreRazon": factura_data["cliente_nombre"]
                },
                "TipoDesglose": {
                    "DesgloseFactura": {
                        "Sujeta": {
                            "NoExenta": {
                                "TipoNoExenta": "S1",
                                "DesgloseIVA": {
                                    "DetalleIVA": [{
                                        "TipoImpositivo": factura_data["tipo_iva"],
                                        "BaseImponible": f"{factura_data['base_imponible']:.2f}",
                                        "CuotaRepercutida": f"{factura_data['cuota_iva']:.2f}"
                                    }]
                                }
                            }
                        }
                    }
                },
                "ImporteTotal": f"{factura_data['total']:.2f}"
            }
            
            # En modo test, simular envío
            if self.environment == "test":
                return {
                    "success": True,
                    "mode": "test",
                    "factura_numero": factura_data["numero"],
                    "estado": "Aceptada (SIMULADO)",
                    "csv": "TEST-CSV-123456789",
                    "mensaje": "Factura procesada en modo TEST. En producción se enviaría a AEAT."
                }
            
            # En producción, enviar a AEAT (requiere certificado digital)
            return {
                "success": False,
                "error": "Producción requiere certificado digital. Configure AEAT_CERTIFICATE_PATH"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def presentar_modelo_303(
        self,
        trimestre: int,
        ejercicio: int,
        datos: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Presentar Modelo 303 (IVA trimestral)
        
        Args:
            trimestre: Trimestre (1, 2, 3, 4)
            ejercicio: Año (YYYY)
            datos: Datos del modelo
                - base_imponible_general: float
                - cuota_iva_soportado: float
                - cuota_iva_repercutido: float
                - resultado: float (a ingresar o devolver)
                
        Returns:
            Dict con resultado de la presentación
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Hacienda service not configured"
            }
        
        try:
            # Calcular resultado
            resultado = datos.get("cuota_iva_repercutido", 0) - datos.get("cuota_iva_soportado", 0)
            
            modelo_data = {
                "modelo": "303",
                "ejercicio": ejercicio,
                "periodo": f"{trimestre}T",
                "base_imponible": datos.get("base_imponible_general", 0),
                "iva_soportado": datos.get("cuota_iva_soportado", 0),
                "iva_repercutido": datos.get("cuota_iva_repercutido", 0),
                "resultado": resultado,
                "tipo_declaracion": "I" if resultado > 0 else "D"  # Ingreso o Devolución
            }
            
            # En modo test
            if self.environment == "test":
                return {
                    "success": True,
                    "mode": "test",
                    "modelo": "303",
                    "periodo": f"{trimestre}T/{ejercicio}",
                    "resultado": f"€{abs(resultado):.2f}",
                    "tipo": "A ingresar" if resultado > 0 else "A devolver",
                    "csv": f"TEST-303-{ejercicio}{trimestre}",
                    "mensaje": "Modelo 303 calculado. En producción se presentaría a AEAT."
                }
            
            return {
                "success": False,
                "error": "Producción requiere certificado digital"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generar_factura_pdf(
        self,
        factura_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generar PDF de factura (sin necesidad de AEAT)
        
        Args:
            factura_data: Datos completos de la factura
            
        Returns:
            Dict con URL del PDF generado
        """
        try:
            # Aquí iría la generación de PDF con ReportLab o WeasyPrint
            # Por ahora, retornar estructura
            
            return {
                "success": True,
                "factura_numero": factura_data.get("numero"),
                "pdf_url": f"/invoices/{factura_data.get('numero')}.pdf",
                "mensaje": "PDF generation placeholder - implement with ReportLab"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado del servicio"""
        return {
            "configured": self.is_configured(),
            "environment": self.environment,
            "nif": self.nif[:3] + "****" + self.nif[-2:] if self.nif else None,
            "sii_enabled": self.is_configured(),
            "modelos_disponibles": ["303", "390", "347"] if self.is_configured() else []
        }


# Instancia global
hacienda_service = HaciendaService()

