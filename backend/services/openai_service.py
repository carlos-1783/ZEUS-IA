"""
⚡ ZEUS-IA OpenAI Service ⚡
Servicio central para interactuar con OpenAI API
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from openai import OpenAI  # pyright: ignore[reportMissingImports]
from config.settings import settings

# Cliente OpenAI global
client = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client instance"""
    global client
    if client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("❌ OPENAI_API_KEY not configured")
        
        try:
            # Inicializar solo con api_key (sin kwargs adicionales)
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=float(getattr(settings, "OPENAI_TIMEOUT_SEC", 120) or 120),
                max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 2) or 2),
            )
            print(f"✅ OpenAI client initialized successfully")
        except TypeError as e:
            # Si falla con parámetros adicionales, intentar solo con api_key
            print(f"⚠️ OpenAI init con parámetros falló: {e}")
            print(f"🔄 Reiniciando con solo api_key...")
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=float(getattr(settings, "OPENAI_TIMEOUT_SEC", 120) or 120),
                max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 2) or 2),
            )
        
    return client


def calculate_cost(usage: Dict[str, int], model: str = "gpt-3.5-turbo") -> float:
    """Calculate cost of API call"""
    # Precios actualizados (Enero 2025)
    costs = {
        "gpt-3.5-turbo": {
            "input": 0.0015 / 1000,  # $0.0015 per 1K tokens
            "output": 0.002 / 1000    # $0.002 per 1K tokens
        },
        "gpt-4-turbo": {
            "input": 0.01 / 1000,
            "output": 0.03 / 1000
        },
        "gpt-4": {
            "input": 0.03 / 1000,
            "output": 0.06 / 1000
        }
    }
    
    model_costs = costs.get(model, costs["gpt-3.5-turbo"])
    
    input_cost = usage.get("prompt_tokens", 0) * model_costs["input"]
    output_cost = usage.get("completion_tokens", 0) * model_costs["output"]
    
    return round(input_cost + output_cost, 6)


def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Wrapper para OpenAI chat completions con telemetría
    
    Args:
        messages: Lista de mensajes [{"role": "system|user|assistant", "content": "..."}]
        model: Modelo a usar (default: settings.OPENAI_MODEL)
        temperature: Temperatura (default: settings.OPENAI_TEMPERATURE)
        max_tokens: Máximo de tokens (default: settings.OPENAI_MAX_TOKENS)
    
    Returns:
        Dict con respuesta y metadata
    """
    start_time = time.time()
    
    # Defaults
    model = model or settings.OPENAI_MODEL
    temperature = temperature if temperature is not None else settings.OPENAI_TEMPERATURE
    max_tokens = max_tokens or settings.OPENAI_MAX_TOKENS
    
    try:
        client = get_openai_client()
        
        print(f"🤖 [OpenAI] Calling {model}...")
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        elapsed_time = time.time() - start_time
        
        # Extract response
        content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        
        # Calculate cost
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        cost = calculate_cost(usage, model)
        
        result = {
            "success": True,
            "content": content,
            "finish_reason": finish_reason,
            "usage": usage,
            "cost": cost,
            "model": model,
            "elapsed_time": round(elapsed_time, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"✅ [OpenAI] Response received in {elapsed_time:.2f}s (${cost:.4f})")
        
        return result
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = str(e)
        print(f"❌ [OpenAI] Error after {elapsed_time:.2f}s: {error_msg}")
        
        # Mensaje más amigable para error 401
        if "401" in error_msg or "insufficient permissions" in error_msg.lower():
            user_friendly_msg = "⚠️ Tu API key de OpenAI no tiene permisos suficientes. Ve a https://platform.openai.com/api-keys y crea una nueva key con permisos completos (Owner/Writer), o activa el scope 'model.request' en tu key actual."
        elif "api_key" in error_msg.lower():
            user_friendly_msg = "❌ API key de OpenAI no configurada o inválida. Verifica OPENAI_API_KEY en Railway."
        elif "context length" in error_msg.lower() or "context_length_exceeded" in error_msg.lower():
            user_friendly_msg = (
                "⚠️ La conversación es demasiado larga para el modelo actual. "
                "Reduce historial o vuelve a intentar para continuar en contexto resumido."
            )
        else:
            user_friendly_msg = error_msg
        
        return {
            "success": False,
            "error": user_friendly_msg,
            "technical_error": error_msg,
            "elapsed_time": round(elapsed_time, 2),
            "timestamp": datetime.now().isoformat()
        }


def parse_json_response(content: str) -> Optional[Dict]:
    """
    Intenta parsear respuesta JSON de OpenAI
    A veces responde con markdown ```json ... ```
    """
    try:
        # Caso 1: JSON directo
        return json.loads(content)
    except json.JSONDecodeError:
        # Caso 2: JSON dentro de markdown
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            json_str = content[start:end].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Caso 3: JSON dentro de backticks
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            json_str = content[start:end].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
    
    return None


def test_connection() -> bool:
    """Test OpenAI API connection"""
    try:
        result = chat_completion(
            messages=[
                {"role": "system", "content": "Eres un asistente de prueba."},
                {"role": "user", "content": "Di 'OK' si me recibes."}
            ],
            max_tokens=10
        )
        
        if result["success"]:
            print(f"✅ OpenAI connection successful!")
            print(f"   Model: {result['model']}")
            print(f"   Response: {result['content']}")
            print(f"   Cost: ${result['cost']:.6f}")
            return True
        else:
            print(f"❌ OpenAI connection failed: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI test failed: {str(e)}")
        return False


# Export main functions
__all__ = [
    "get_openai_client",
    "chat_completion",
    "parse_json_response",
    "calculate_cost",
    "test_connection"
]

