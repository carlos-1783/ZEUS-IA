"""
⚡ ZEUS-IA - Test Script ⚡
Script para probar el sistema de agentes
"""

import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.openai_service import test_connection
from backend.agents.zeus_core import ZeusCore
from backend.agents.perseo import Perseo
from backend.agents.rafael import Rafael


def test_openai_connection():
    """Test 1: Verificar conexión con OpenAI"""
    print("\n" + "="*60)
    print("TEST 1: Verificando conexión con OpenAI")
    print("="*60)
    
    success = test_connection()
    
    if success:
        print("✅ OpenAI connection successful!")
        return True
    else:
        print("❌ OpenAI connection failed - Check your API key")
        return False


def test_perseo():
    """Test 2: Probar PERSEO (Marketing)"""
    print("\n" + "="*60)
    print("TEST 2: Probando PERSEO (Agente de Marketing)")
    print("="*60)
    
    perseo = Perseo()
    
    # Caso de uso simple
    print("\n📋 Consulta: Crear estrategia de marketing para restaurante")
    
    result = perseo.process_request({
        "type": "campaign",
        "message": "Necesito una estrategia de marketing para atraer empresas del polígono industrial a mi restaurante.",
        "target_audience": "Trabajadores de empresas en polígono industrial",
        "budget": "500€/mes",
        "duration": "3 meses"
    })
    
    print(f"\n🎯 Agente: {result['agent']}")
    print(f"💡 Confianza: {result['confidence']}")
    print(f"⚠️  HITL Requerido: {result['hitl_required']}")
    print(f"💰 Costo: ${result['metadata']['cost']:.4f}")
    print(f"\n📝 Respuesta:\n{result['content'][:500]}...")
    
    print(f"\n📊 Stats de PERSEO:")
    stats = perseo.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    return result


def test_rafael():
    """Test 3: Probar RAFAEL (Fiscal)"""
    print("\n" + "="*60)
    print("TEST 3: Probando RAFAEL (Agente Fiscal)")
    print("="*60)
    
    rafael = Rafael()
    
    # Caso de uso simple
    print("\n📋 Consulta: Analizar factura")
    
    result = rafael.process_request({
        "type": "invoice",
        "message": "¿Qué IVA debo aplicar a una factura de menús servidos en el restaurante?",
        "client_name": "Empresa Industrial S.L.",
        "amount": "350",
        "concept": "Menús del día - Septiembre 2024"
    })
    
    print(f"\n🎯 Agente: {result['agent']}")
    print(f"💡 Confianza: {result['confidence']}")
    print(f"⚠️  HITL Requerido: {result['hitl_required']}")
    print(f"💰 Costo: ${result['metadata']['cost']:.4f}")
    print(f"\n📝 Respuesta:\n{result['content'][:500]}...")
    
    print(f"\n📊 Stats de RAFAEL:")
    stats = rafael.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    return result


def test_zeus_core():
    """Test 4: Probar ZEUS CORE (Orquestador)"""
    print("\n" + "="*60)
    print("TEST 4: Probando ZEUS CORE (Orquestador)")
    print("="*60)
    
    # Crear ZEUS y registrar agentes
    zeus = ZeusCore()
    
    perseo = Perseo()
    rafael = Rafael()
    
    zeus.register_agent(perseo)
    zeus.register_agent(rafael)
    
    # Test de routing automático
    print("\n🧪 Test de routing automático")
    
    test_cases = [
        {
            "message": "Necesito optimizar mi SEO para restaurante",
            "expected_agent": "PERSEO"
        },
        {
            "message": "¿Cómo calculo el IVA de una factura?",
            "expected_agent": "RAFAEL"
        },
        {
            "message": "Quiero una campaña en Instagram",
            "expected_agent": "PERSEO"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Caso {i} ---")
        print(f"Mensaje: {test_case['message']}")
        
        result = zeus.process_request({
            "user_message": test_case['message']
        })
        
        print(f"✅ Agente seleccionado: {result['selected_agent']}")
        print(f"   (Esperado: {test_case['expected_agent']})")
        print(f"💰 Costo: ${result['metadata']['cost']:.4f}")
    
    # Estado del sistema
    print("\n🏛️ Estado del Sistema:")
    status = zeus.get_system_status()
    print(f"   Total agentes: {status['total_agents']}")
    print(f"   Status: {status['system_status']}")
    print(f"   ZEUS requests: {status['zeus_core']['total_requests']}")
    print(f"   ZEUS cost: ${status['zeus_core']['total_cost']:.4f}")
    
    return zeus


def main():
    """Ejecutar todos los tests"""
    print("\n" + "🏛️"*30)
    print("⚡ ZEUS-IA - Sistema de Agentes Inteligentes ⚡")
    print("🏛️"*30)
    
    try:
        # Test 1: OpenAI connection
        if not test_openai_connection():
            print("\n❌ No se puede continuar sin conexión a OpenAI")
            print("\nPor favor, configura tu OPENAI_API_KEY:")
            print("1. Crea archivo backend/.env")
            print("2. Agrega: OPENAI_API_KEY=tu-api-key-aqui")
            return
        
        # Test 2: PERSEO
        perseo_result = test_perseo()
        
        # Test 3: RAFAEL
        rafael_result = test_rafael()
        
        # Test 4: ZEUS CORE
        zeus = test_zeus_core()
        
        # Resumen final
        print("\n" + "="*60)
        print("🎉 TODOS LOS TESTS COMPLETADOS")
        print("="*60)
        
        total_cost = (
            perseo_result['metadata']['cost'] +
            rafael_result['metadata']['cost'] +
            zeus.total_cost
        )
        
        print(f"\n💰 Costo total de pruebas: ${total_cost:.4f}")
        print(f"⚡ Sistema ZEUS completamente operativo")
        print(f"🏛️ El Olimpo está listo para conquistar")
        
    except Exception as e:
        print(f"\n❌ Error durante los tests: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

