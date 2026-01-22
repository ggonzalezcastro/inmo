"""
Script de pruebas para el sistema de agendas
Este script crea datos de prueba y prueba los endpoints de appointments
"""
import asyncio
import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.lead import Lead, LeadStatus
from app.models.user import User
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.services.appointment_service import AppointmentService
from app.services.lead_service import LeadService
from app.schemas.lead import LeadCreate
import hashlib

CHILE_TZ = pytz.timezone('America/Santiago')


async def create_test_data():
    """Crear datos de prueba: usuario y lead"""
    async with AsyncSessionLocal() as db:
        try:
            # Crear usuario de prueba (agente)
            from sqlalchemy.future import select
            from passlib.context import CryptContext
            
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            # Verificar si ya existe un usuario de prueba
            result = await db.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalars().first()
            
            if not user:
                hashed_password = pwd_context.hash("test123")
                user = User(
                    email="test@example.com",
                    hashed_password=hashed_password,
                    broker_name="Agente de Prueba",
                    role="broker",
                    is_active=True
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                print(f"✅ Usuario creado: {user.id} - {user.email}")
            else:
                print(f"✅ Usuario existente: {user.id} - {user.email}")
            
            # Crear lead de prueba
            result = await db.execute(
                select(Lead).where(Lead.phone == "+56912345678")
            )
            lead = result.scalars().first()
            
            if not lead:
                lead_data = LeadCreate(
                    phone="+56912345678",
                    name="Lead de Prueba",
                    email="lead@example.com",
                    tags=["test", "appointment"]
                )
                lead = await LeadService.create_lead(db, lead_data)
                print(f"✅ Lead creado: {lead.id} - {lead.name} ({lead.phone})")
            else:
                print(f"✅ Lead existente: {lead.id} - {lead.name} ({lead.phone})")
            
            return user, lead
            
        except Exception as e:
            print(f"❌ Error creando datos de prueba: {str(e)}")
            await db.rollback()
            raise


async def test_create_appointment(user_id: int, lead_id: int):
    """Probar crear una cita"""
    async with AsyncSessionLocal() as db:
        try:
            print("\n📅 Probando crear una cita...")
            
            # Crear cita para mañana a las 14:00
            tomorrow = datetime.now(CHILE_TZ) + timedelta(days=1)
            start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
            
            appointment = await AppointmentService.create_appointment(
                db=db,
                lead_id=lead_id,
                start_time=start_time,
                duration_minutes=60,
                appointment_type=AppointmentType.VIRTUAL_MEETING,
                agent_id=user_id,
                location="Reunión virtual",
                notes="Cita de prueba generada automáticamente"
            )
            
            print(f"✅ Cita creada exitosamente:")
            print(f"   ID: {appointment.id}")
            print(f"   Fecha/Hora: {appointment.start_time}")
            print(f"   Duración: {appointment.duration_minutes} minutos")
            print(f"   Estado: {appointment.status}")
            print(f"   Google Meet URL: {appointment.meet_url}")
            if appointment.google_event_id:
                print(f"   Google Event ID: {appointment.google_event_id}")
            else:
                print(f"   ⚠️  Google Event ID no generado (Google Calendar no configurado)")
            
            return appointment
            
        except Exception as e:
            print(f"❌ Error creando cita: {str(e)}")
            await db.rollback()
            raise


async def test_list_appointments():
    """Probar listar citas"""
    async with AsyncSessionLocal() as db:
        try:
            print("\n📋 Probando listar citas...")
            
            from sqlalchemy.future import select
            result = await db.execute(
                select(Appointment).order_by(Appointment.start_time.desc()).limit(10)
            )
            appointments = result.scalars().all()
            
            print(f"✅ Encontradas {len(appointments)} citas:")
            for apt in appointments:
                print(f"   - ID: {apt.id}, Fecha: {apt.start_time}, Estado: {apt.status}, Meet: {apt.meet_url[:50] if apt.meet_url else 'N/A'}...")
            
            return appointments
            
        except Exception as e:
            print(f"❌ Error listando citas: {str(e)}")
            raise


async def test_get_available_slots(user_id: int):
    """Probar obtener horarios disponibles"""
    async with AsyncSessionLocal() as db:
        try:
            print("\n🕐 Probando obtener horarios disponibles...")
            
            start_date = datetime.now(CHILE_TZ).date()
            end_date = start_date + timedelta(days=7)
            
            slots = await AppointmentService.get_available_slots(
                db=db,
                start_date=start_date,
                end_date=end_date,
                agent_id=user_id,
                duration_minutes=60
            )
            
            print(f"✅ Encontrados {len(slots)} horarios disponibles:")
            for slot in slots[:5]:  # Mostrar solo los primeros 5
                print(f"   - {slot['date']} a las {slot['time']}")
            
            if len(slots) > 5:
                print(f"   ... y {len(slots) - 5} más")
            
            return slots
            
        except Exception as e:
            print(f"❌ Error obteniendo horarios: {str(e)}")
            raise


async def test_confirm_appointment(appointment_id: int):
    """Probar confirmar una cita"""
    async with AsyncSessionLocal() as db:
        try:
            print(f"\n✅ Probando confirmar cita {appointment_id}...")
            
            appointment = await AppointmentService.confirm_appointment(db, appointment_id)
            
            print(f"✅ Cita confirmada exitosamente:")
            print(f"   ID: {appointment.id}")
            print(f"   Estado: {appointment.status}")
            
            return appointment
            
        except Exception as e:
            print(f"❌ Error confirmando cita: {str(e)}")
            await db.rollback()
            raise


async def main():
    """Función principal"""
    print("=" * 60)
    print("🧪 SCRIPT DE PRUEBAS PARA SISTEMA DE AGENDAS")
    print("=" * 60)
    
    try:
        # 1. Crear datos de prueba
        print("\n1️⃣ Creando datos de prueba...")
        user, lead = await create_test_data()
        
        # 2. Crear una cita
        print("\n2️⃣ Creando una cita de prueba...")
        appointment = await test_create_appointment(user.id, lead.id)
        
        # 3. Listar citas
        print("\n3️⃣ Listando citas...")
        await test_list_appointments()
        
        # 4. Obtener horarios disponibles
        print("\n4️⃣ Obteniendo horarios disponibles...")
        await test_get_available_slots(user.id)
        
        # 5. Confirmar la cita
        print("\n5️⃣ Confirmando la cita creada...")
        await test_confirm_appointment(appointment.id)
        
        print("\n" + "=" * 60)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("=" * 60)
        print("\n📝 Notas:")
        print("   - Usuario de prueba: test@example.com / test123")
        print("   - Lead de prueba: +56912345678")
        print("   - Para probar con Google Calendar real, configura las variables de entorno")
        print("     (ver ENV_VARIABLES.md)")
        
    except Exception as e:
        print(f"\n❌ Error en las pruebas: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

