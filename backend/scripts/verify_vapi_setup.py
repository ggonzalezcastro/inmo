#!/usr/bin/env python3
"""
Script to verify Vapi.ai setup
Usage: python scripts/verify_vapi_setup.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings


def check_env_var(name: str, value: str, required: bool = True) -> bool:
    """Check if environment variable is set"""
    
    if not value or value == "":
        if required:
            print(f"❌ {name}: NO CONFIGURADA (Requerida)")
            return False
        else:
            print(f"⚠️  {name}: No configurada (Opcional)")
            return True
    
    # Show first 10 chars
    display_value = value[:10] + "..." if len(value) > 10 else value
    print(f"✅ {name}: {display_value}")
    return True


def main():
    print("🔍 Verificando Configuración de Vapi.ai\n")
    print("=" * 60)
    
    all_ok = True
    
    # Check Vapi credentials
    print("\n📌 Credenciales de Vapi:")
    all_ok &= check_env_var("VAPI_API_KEY", settings.VAPI_API_KEY, required=True)
    all_ok &= check_env_var("VAPI_PHONE_NUMBER_ID", settings.VAPI_PHONE_NUMBER_ID, required=True)
    check_env_var("VAPI_ASSISTANT_ID", settings.VAPI_ASSISTANT_ID, required=False)
    if not settings.VAPI_ASSISTANT_ID:
        print("   (O configura assistant_id_default en BrokerVoiceConfig por broker)")
    
    # Check general settings
    print("\n📌 Configuración General:")
    check_env_var("WEBHOOK_BASE_URL", settings.WEBHOOK_BASE_URL, required=True)
    
    if settings.WEBHOOK_BASE_URL == "http://localhost:8000":
        print("   ⚠️  ADVERTENCIA: WEBHOOK_BASE_URL apunta a localhost")
        print("   Para producción, debe ser una URL pública (ej: https://tu-backend.railway.app)")
    
    print("\n" + "=" * 60)
    
    if all_ok:
        print("\n✅ ¡TODO CONFIGURADO CORRECTAMENTE!\n")
        print("🎯 Próximos pasos:")
        print("   1. Crear asistente: python scripts/create_vapi_assistant.py")
        print("   2. Probar llamada: python scripts/test_vapi_call.py +56912345678")
        print("   3. Ver dashboard: https://dashboard.vapi.ai")
    else:
        print("\n⚠️  CONFIGURACIÓN INCOMPLETA\n")
        print("📋 Para completar la configuración:")
        print("   1. Crea cuenta en: https://vapi.ai")
        print("   2. Obtén API Key en: Settings → API Keys")
        print("   3. Compra número en: Phone Numbers")
        print("   4. Actualiza tu .env con las credenciales")
        print("\n📖 Guía completa: Ver VAPI_MIGRATION_GUIDE.md")
        sys.exit(1)


if __name__ == "__main__":
    main()
