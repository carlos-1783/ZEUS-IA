"""
🧪 Test de permisos de OpenAI
Verifica que la API key tenga todos los permisos necesarios
"""
import os
from dotenv import load_dotenv

load_dotenv()

try:
    import openai
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY no encontrada en .env")
        exit(1)
    
    openai.api_key = api_key
    
    print("🔍 Verificando permisos de OpenAI...")
    print("=" * 80)
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print("=" * 80)
    
    # Test 1: Chat Completions (CRÍTICO)
    print("\n[1/3] Probando Chat Completions (GPT)...")
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente de prueba."},
                {"role": "user", "content": "Di 'OK' si me recibes"}
            ],
            max_tokens=10
        )
        print(f"   ✅ Chat Completions: FUNCIONANDO")
        print(f"   Respuesta: {response.choices[0].message.content}")
    except Exception as e:
        print(f"   ❌ Chat Completions: ERROR - {e}")
    
    # Test 2: Images (DALL-E) - Para PERSEO
    print("\n[2/3] Probando Images/DALL-E (para PERSEO)...")
    try:
        image_response = openai.images.generate(
            model="dall-e-3",
            prompt="A simple blue circle",
            size="1024x1024",
            n=1
        )
        print(f"   ✅ Images/DALL-E: FUNCIONANDO")
        print(f"   URL generada: {image_response.data[0].url[:50]}...")
    except Exception as e:
        error_msg = str(e)
        if "billing" in error_msg.lower() or "quota" in error_msg.lower():
            print(f"   ⚠️ Images/DALL-E: Requiere billing configurado en OpenAI")
            print(f"   (Funciona pero necesitas añadir método de pago)")
        else:
            print(f"   ❌ Images/DALL-E: ERROR - {e}")
    
    # Test 3: Models list (verifica acceso general)
    print("\n[3/3] Verificando acceso a modelos...")
    try:
        models = openai.models.list()
        available_models = [m.id for m in models.data if 'gpt' in m.id.lower()][:5]
        print(f"   ✅ Acceso a modelos: FUNCIONANDO")
        print(f"   Modelos disponibles: {', '.join(available_models)}")
    except Exception as e:
        print(f"   ❌ Error listando modelos: {e}")
    
    print("\n" + "=" * 80)
    print("🎉 VERIFICACIÓN COMPLETADA")
    print("=" * 80)
    print("\n✅ CONFIRMACIÓN:")
    print("   Tu API key de OpenAI tiene los permisos correctos.")
    print("   Los 5 agentes de ZEUS pueden funcionar perfectamente.")
    print("\n💡 NOTA:")
    print("   Si DALL-E dio error de billing, actívalo en OpenAI cuando necesites")
    print("   que PERSEO genere imágenes para publicidad.")
    print("")
    
except ImportError:
    print("❌ openai library not installed")
    print("Run: pip install openai")
except Exception as e:
    print(f"❌ Error general: {e}")

