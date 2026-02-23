#!/usr/bin/env python3
"""
Script to test Vapi.ai phone call
Usage: python scripts/test_vapi_call.py +56912345678
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.voice import VapiProvider
from app.config import settings


async def test_call(phone_number: str):
    """Test Vapi call to a phone number"""
    
    print(f"📞 Prueba de Llamada con Vapi.ai\n")
    print("=" * 60)
    
    # Verify configuration
    if not settings.VAPI_API_KEY:
        print("❌ Error: VAPI_API_KEY no configurada")
        sys.exit(1)
    
    if not settings.VAPI_PHONE_NUMBER_ID:
        print("❌ Error: VAPI_PHONE_NUMBER_ID no configurada")
        sys.exit(1)
    
    if not settings.VAPI_ASSISTANT_ID:
        print("❌ Error: VAPI_ASSISTANT_ID no configurada")
        sys.exit(1)
    
    print(f"✅ API Key: {settings.VAPI_API_KEY[:10]}...")
    print(f"✅ Phone Number ID: {settings.VAPI_PHONE_NUMBER_ID[:10]}...")
    print(f"✅ Assistant ID: {settings.VAPI_ASSISTANT_ID[:10]}...")
    print("=" * 60)
    print()
    
    # Initialize provider
    provider = VapiProvider()
    
    print(f"🎯 Llamando a: {phone_number}")
    print(f"⏳ Iniciando llamada...\n")
    
    try:
        webhook_url = f"{getattr(settings, 'WEBHOOK_BASE_URL', 'http://localhost:8000')}/api/v1/calls/webhooks/voice"
        context = {
            "test": True,
            "lead_id": 999,
            "campaign_id": None,
            "assistant_id": getattr(settings, "VAPI_ASSISTANT_ID", None) or None,
        }
        call_id = await provider.make_call(
            phone=phone_number,
            webhook_url=webhook_url,
            context=context,
        )
        
        print("✅ ¡Llamada iniciada exitosamente!")
        print("=" * 60)
        print(f"Call ID: {call_id}")
        print("=" * 60)
        print()
        
        print("📊 Monitorea la llamada:")
        print(f"   1. Dashboard: https://dashboard.vapi.ai/calls/{call_id}")
        print(f"   2. Tu backend recibirá webhooks en tiempo real")
        print()
        
        print("🎧 Qué esperar:")
        print("   1. El teléfono sonará en unos segundos")
        print("   2. El asistente de IA comenzará la conversación")
        print("   3. Habla naturalmente en español")
        print("   4. El asistente calificará el lead automáticamente")
        print()
        
        # Wait a bit and check status
        print("⏳ Esperando 5 segundos para verificar estado...")
        await asyncio.sleep(5)
        
        status = await provider.get_call_status(call_id)
        print("\n📋 Estado actual:")
        print(f"   Status: {status.get('status')}")
        print(f"   From: {status.get('from')}")
        print(f"   To: {status.get('to')}")
        
        if status.get('status') == 'in-progress':
            print("\n✅ ¡La llamada está en progreso!")
        elif status.get('status') == 'queued':
            print("\n⏳ La llamada está en cola...")
        elif status.get('status') == 'ringing':
            print("\n📞 El teléfono está sonando...")
        
        print()
        
    except Exception as e:
        print(f"\n❌ Error al realizar llamada:")
        print(f"   {str(e)}\n")
        print("Posibles soluciones:")
        print("1. Verifica que el número sea válido en formato E.164 (ej: +56912345678)")
        print("2. Verifica que tengas créditos en tu cuenta de Vapi")
        print("3. Verifica que el PHONE_NUMBER_ID sea correcto")
        print("4. Revisa los logs de Vapi en https://dashboard.vapi.ai")
        sys.exit(1)


async def main():
    if len(sys.argv) < 2:
        print("❌ Error: Falta el número de teléfono")
        print("\nUso:")
        print("   python scripts/test_vapi_call.py +56912345678")
        print("\nFormato:")
        print("   - Usa formato E.164 (con +)")
        print("   - Chile: +56912345678")
        print("   - México: +525512345678")
        print("   - USA: +15551234567")
        sys.exit(1)
    
    phone = sys.argv[1]
    
    # Validate format
    if not phone.startswith('+'):
        print("⚠️  Advertencia: El número debe comenzar con +")
        print(f"   ¿Quisiste decir: +{phone}?")
        response = input("   Continuar de todos modos? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    await test_call(phone)


if __name__ == "__main__":
    asyncio.run(main())
