#!/usr/bin/env python3
"""Script para verificar si existe un lead con id 12 y nombre andres"""

import asyncio
import sys
import os

# Agregar el directorio backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from app.models.lead import Lead
from app.config import settings

async def check_lead():
    # Crear engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Buscar lead con id 12
        result = await session.execute(
            select(Lead).where(Lead.id == 12)
        )
        lead = result.scalar_one_or_none()
        
        if lead:
            print(f"✅ Lead encontrado con ID 12:")
            print(f"   Nombre: {lead.name}")
            print(f"   Teléfono: {lead.phone}")
            print(f"   Email: {lead.email}")
            print(f"   Pipeline Stage: {lead.pipeline_stage}")
            print(f"   Score: {lead.lead_score}")
            print(f"   Status: {lead.status}")
            
            # Verificar si el nombre contiene "andres"
            if lead.name and "andres" in lead.name.lower():
                print(f"\n✅ El nombre contiene 'andres'")
            else:
                print(f"\n⚠️  El nombre NO contiene 'andres' (nombre actual: '{lead.name}')")
        else:
            print("❌ No se encontró lead con ID 12")
        
        # También buscar todos los leads con nombre que contenga "andres"
        print("\n" + "="*50)
        result2 = await session.execute(
            select(Lead).where(Lead.name.ilike('%andres%'))
        )
        andres_leads = result2.scalars().all()
        
        if andres_leads:
            print(f"📋 Leads con nombre 'andres' encontrados: {len(andres_leads)}")
            for l in andres_leads:
                print(f"   ID: {l.id}, Nombre: {l.name}, Teléfono: {l.phone}, Stage: {l.pipeline_stage}")
        else:
            print("❌ No se encontraron leads con nombre 'andres'")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_lead())

