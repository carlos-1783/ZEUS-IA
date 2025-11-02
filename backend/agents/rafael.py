"""
⚡ RAFAEL - Guardián Fiscal ⚡
Agente especializado en Fiscalidad y Contabilidad
"""

import json
from typing import Dict, Any
from agents.base_agent import BaseAgent


class Rafael(BaseAgent):
    """
    RAFAEL - Guardián fiscal
    Especializado en fiscalidad española, contabilidad y cumplimiento
    """
    
    def __init__(self):
        # Cargar configuración desde prompts.json
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_path = os.path.join(base_dir, "config", "prompts.json")
        with open(prompts_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        rafael_config = config["zeus_prime_v1"]["agents"]["RAFAEL"]
        
        super().__init__(
            name="RAFAEL",
            role=rafael_config["role"],
            system_prompt=rafael_config["prompt"],
            temperature=rafael_config["parameters"]["temperature"],
            max_tokens=rafael_config["parameters"]["max_tokens"],
            hitl_threshold=rafael_config["parameters"]["hitl_threshold"]
        )
        
        self.domain = rafael_config["parameters"]["domain"]
        self.country = rafael_config["parameters"]["country"]
        
        print(f"📊 RAFAEL inicializado - Dominio: {self.domain} ({self.country})")
    
    def process_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesar solicitud fiscal/contable
        
        Casos de uso:
        - Generar facturas
        - Analizar gastos deducibles
        - Calcular IVA/IRPF
        - Asesorar sobre modelos (303, 390, etc.)
        - Optimización fiscal
        """
        request_type = context.get("type", "general")
        user_message = context.get("message", context.get("user_message", ""))
        
        # Agregar contexto específico fiscal si es necesario
        if request_type == "invoice":
            enhanced_message = self._enhance_invoice_request(user_message, context)
        elif request_type == "tax":
            enhanced_message = self._enhance_tax_request(user_message, context)
        elif request_type == "deduction":
            enhanced_message = self._enhance_deduction_request(user_message, context)
        else:
            enhanced_message = user_message
        
        # Hacer decisión
        result = self.make_decision(enhanced_message, additional_context=context)
        
        # RAFAEL-specific metadata
        result["domain"] = self.domain
        result["country"] = self.country
        result["request_type"] = request_type
        
        return result
    
    def _enhance_invoice_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de factura"""
        client_name = context.get("client_name", "no especificado")
        amount = context.get("amount", "no especificado")
        concept = context.get("concept", "no especificado")
        
        enhanced = f"""{message}

Datos de la factura:
- Cliente: {client_name}
- Importe: {amount}€
- Concepto: {concept}

Por favor, proporciona:
1. IVA aplicable (21%, 10%, 4% o exento)
2. Retención IRPF si aplica
3. Total a facturar
4. Formato recomendado
5. Información adicional requerida según normativa
"""
        return enhanced
    
    def _enhance_tax_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud fiscal"""
        period = context.get("period", "no especificado")
        tax_type = context.get("tax_type", "no especificado")
        
        enhanced = f"""{message}

Contexto fiscal:
- Período: {period}
- Tipo de impuesto: {tax_type}

Por favor, proporciona:
1. Normativa aplicable
2. Cálculo detallado
3. Fecha límite de presentación
4. Documentación necesaria
5. Posibles deducciones u optimizaciones
"""
        return enhanced
    
    def _enhance_deduction_request(self, message: str, context: Dict) -> str:
        """Enriquecer solicitud de deducción"""
        expense_type = context.get("expense_type", "no especificado")
        amount = context.get("amount", "no especificado")
        
        enhanced = f"""{message}

Gasto a analizar:
- Tipo: {expense_type}
- Importe: {amount}€

Por favor, determina:
1. ¿Es deducible? (sí/no/parcial)
2. Porcentaje de deducción aplicable
3. Requisitos para la deducción (factura, justificación, etc.)
4. IVA deducible
5. Documentación necesaria
"""
        return enhanced
    
    def check_hitl_required(self, decision: Dict) -> bool:
        """
        RAFAEL requiere HITL para:
        - Importes >5000€
        - Incertidumbre >10% en cálculos
        - Normativa ambigua
        - Decisiones que afecten declaraciones oficiales
        """
        # Check base
        if super().check_hitl_required(decision):
            return True
        
        content = decision.get("content", "").lower()
        
        # Detectar importes altos
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?', content)
        for num_str in numbers:
            try:
                amount = float(num_str.replace(',', '.'))
                if amount > 5000:
                    print(f"⚠️ [HITL] RAFAEL: Importe alto detectado (>{amount}€)")
                    return True
            except ValueError:
                pass
        
        # Detectar variaciones >10%
        if "variación" in content or "diferencia" in content:
            for num_str in numbers:
                try:
                    percentage = float(num_str.replace(',', '.'))
                    if percentage > 10:
                        print(f"⚠️ [HITL] RAFAEL: Variación >10% detectada")
                        return True
                except ValueError:
                    pass
        
        # Detectar palabras de incertidumbre fiscal
        uncertain_keywords = [
            "ambiguo", "poco claro", "interpretación", "consulta vinculante",
            "requiere asesor", "caso especial", "normativa nueva"
        ]
        if any(kw in content for kw in uncertain_keywords):
            print(f"⚠️ [HITL] RAFAEL: Incertidumbre normativa detectada")
            return True
        
        return False

