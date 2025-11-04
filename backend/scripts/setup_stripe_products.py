"""
🔧 Script para configurar productos y precios en Stripe
Crea los 4 planes de ZEUS-IA con setup fees y suscripciones
"""
import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
import stripe  # pyright: ignore[reportMissingImports]

# Cargar variables de entorno
load_dotenv()

# Configurar Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

def create_stripe_products():
    """Crear productos y precios en Stripe"""
    
    print("🚀 Configurando productos en Stripe...")
    print("=" * 80)
    
    # Definición de productos según MODELO_PRECIOS_ZEUS.md
    products_config = [
        {
            "name": "ZEUS STARTUP",
            "description": "Plan ideal para autónomos y pequeños estudios (1-5 empleados)",
            "setup_price": 50000,  # €500 en centavos
            "monthly_price": 9900,  # €99 en centavos
            "features": [
                "5 Agentes IA (ZEUS, PERSEO, RAFAEL, THALOS, JUSTICIA)",
                "WhatsApp Automation",
                "Email Automation",
                "Facturación + Hacienda",
                "Stripe Payments",
                "Soporte por email"
            ]
        },
        {
            "name": "ZEUS GROWTH",
            "description": "Plan profesional para PYMEs en crecimiento (6-25 empleados)",
            "setup_price": 150000,  # €1,500
            "monthly_price": 29900,  # €299
            "features": [
                "Todo de ZEUS STARTUP",
                "Google Workspace (Calendar, Gmail, Drive, Sheets)",
                "Marketing Automation (Google Ads, Meta Ads)",
                "Analytics avanzado",
                "Soporte prioritario",
                "Onboarding personalizado"
            ]
        },
        {
            "name": "ZEUS BUSINESS",
            "description": "Plan empresarial para empresas establecidas (26-100 empleados)",
            "setup_price": 250000,  # €2,500
            "monthly_price": 69900,  # €699
            "features": [
                "Todo de ZEUS GROWTH",
                "Integraciones personalizadas",
                "Múltiples usuarios admin",
                "API access completo",
                "Soporte 24/7",
                "Account manager dedicado",
                "SLA garantizado"
            ]
        },
        {
            "name": "ZEUS ENTERPRISE",
            "description": "Plan corporativo para grandes organizaciones (101+ empleados)",
            "setup_price": 500000,  # €5,000
            "monthly_price": 150000,  # €1,500
            "features": [
                "Todo de ZEUS BUSINESS",
                "Instalación on-premise (opcional)",
                "White-label disponible",
                "Integraciones enterprise (SAP, Oracle)",
                "Compliance y auditorías",
                "Training presencial",
                "Contrato enterprise SLA 99.9%",
                "Soporte técnico dedicado"
            ]
        }
    ]
    
    created_products = []
    
    for product_config in products_config:
        try:
            print(f"\n📦 Creando producto: {product_config['name']}")
            
            # Crear producto en Stripe
            product = stripe.Product.create(
                name=product_config['name'],
                description=product_config['description'],
                metadata={
                    'type': 'zeus_subscription',
                    'features': ', '.join(product_config['features'])
                }
            )
            
            print(f"   ✅ Producto creado: {product.id}")
            
            # Crear precio de setup (one-time)
            setup_price = stripe.Price.create(
                product=product.id,
                unit_amount=product_config['setup_price'],
                currency='eur',
                metadata={
                    'type': 'setup_fee',
                    'plan_name': product_config['name']
                }
            )
            
            print(f"   ✅ Setup fee: €{product_config['setup_price']/100} ({setup_price.id})")
            
            # Crear precio de suscripción (recurring)
            monthly_price = stripe.Price.create(
                product=product.id,
                unit_amount=product_config['monthly_price'],
                currency='eur',
                recurring={
                    'interval': 'month'
                },
                metadata={
                    'type': 'subscription',
                    'plan_name': product_config['name']
                }
            )
            
            print(f"   ✅ Suscripción: €{product_config['monthly_price']/100}/mes ({monthly_price.id})")
            
            created_products.append({
                'name': product_config['name'],
                'product_id': product.id,
                'setup_price_id': setup_price.id,
                'monthly_price_id': monthly_price.id,
                'setup_amount': product_config['setup_price'] / 100,
                'monthly_amount': product_config['monthly_price'] / 100
            })
            
        except stripe.error.StripeError as e:
            print(f"   ❌ Error creando {product_config['name']}: {e}")
            continue
    
    # Resumen
    print("\n" + "=" * 80)
    print("✅ CONFIGURACIÓN COMPLETADA")
    print("=" * 80)
    
    for product in created_products:
        print(f"\n📋 {product['name']}:")
        print(f"   Product ID: {product['product_id']}")
        print(f"   Setup Price ID: {product['setup_price_id']} (€{product['setup_amount']})")
        print(f"   Monthly Price ID: {product['monthly_price_id']} (€{product['monthly_amount']}/mes)")
    
    # Guardar IDs en archivo .env.stripe
    print("\n💾 Guardando IDs en .env.stripe...")
    
    with open('.env.stripe', 'w') as f:
        f.write("# IDs de productos y precios de Stripe\n")
        f.write("# Generado automáticamente por setup_stripe_products.py\n\n")
        
        for i, product in enumerate(created_products):
            plan_name = product['name'].replace(' ', '_').upper()
            f.write(f"# {product['name']}\n")
            f.write(f"{plan_name}_PRODUCT_ID={product['product_id']}\n")
            f.write(f"{plan_name}_SETUP_PRICE_ID={product['setup_price_id']}\n")
            f.write(f"{plan_name}_MONTHLY_PRICE_ID={product['monthly_price_id']}\n\n")
    
    print("   ✅ Archivo .env.stripe creado")
    
    print("\n" + "=" * 80)
    print("🎉 ¡STRIPE CONFIGURADO CORRECTAMENTE!")
    print("=" * 80)
    print("\n📝 Próximos pasos:")
    print("1. Copia el contenido de .env.stripe a tu .env principal")
    print("2. Configura el webhook en Stripe Dashboard:")
    print(f"   URL: https://zeus-ia-production-16d8.up.railway.app/api/v1/integrations/stripe/webhook")
    print("   Eventos: payment_intent.succeeded, customer.subscription.*")
    print("3. Prueba el checkout con tarjeta de test: 4242 4242 4242 4242")
    
    return created_products

if __name__ == "__main__":
    try:
        products = create_stripe_products()
        print(f"\n✅ {len(products)} productos creados exitosamente")
    except Exception as e:
        print(f"\n❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
