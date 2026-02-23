#!/usr/bin/env python3
"""
Script to list all Vapi.ai assistants
Usage: python scripts/list_vapi_assistants.py
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.voice import VapiAssistantService
from app.config import settings


async def main():
    print("🤖 Listando Asistentes de Vapi.ai\n")
    
    if not settings.VAPI_API_KEY:
        print("❌ Error: VAPI_API_KEY no está configurada en el .env")
        sys.exit(1)
    
    try:
        assistants = await VapiAssistantService.list_assistants()
        
        if not assistants:
            print("📭 No tienes asistentes creados todavía")
            print("\n💡 Crea uno con:")
            print("   python scripts/create_vapi_assistant.py")
            return
        
        print(f"✅ Encontrados {len(assistants)} asistente(s)\n")
        print("=" * 80)
        
        for i, assistant in enumerate(assistants, 1):
            print(f"\n{i}. {assistant.get('name', 'Sin nombre')}")
            print(f"   ID: {assistant.get('id')}")
            print(f"   Model: {assistant.get('model', {}).get('model', 'N/A')}")
            print(f"   Voice: {assistant.get('voice', {}).get('voiceId', 'N/A')}")
            
            if assistant.get('firstMessage'):
                first_msg = assistant['firstMessage']
                if len(first_msg) > 60:
                    first_msg = first_msg[:60] + "..."
                print(f"   First Message: {first_msg}")
            
            print()
        
        print("=" * 80)
        print("\n💡 Para usar un asistente, agrega a tu .env:")
        print(f"   VAPI_ASSISTANT_ID={assistants[0].get('id')}")
        print("\n📝 Para ver/editar: https://dashboard.vapi.ai/assistants")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
