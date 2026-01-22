"""
Script simple para crear superadmin
Uso: python3 create_superadmin_simple.py <email> <password> [name]
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from app.models.user import User, UserRole
from app.middleware.auth import hash_password
from app.config import settings


async def create_superadmin(email: str, password: str, name: str = "Super Admin"):
    """Create a superadmin user"""
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            # Check if user exists
            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalars().first()
            
            if existing:
                if existing.role == UserRole.SUPERADMIN:
                    print(f"✅ Superadmin already exists: {email}")
                    existing.hashed_password = hash_password(password)
                    existing.name = name
                    existing.broker_id = None
                    await db.commit()
                    print(f"✅ Password and name updated")
                    return
                else:
                    # Update to superadmin
                    existing.role = UserRole.SUPERADMIN
                    existing.hashed_password = hash_password(password)
                    existing.name = name
                    existing.broker_id = None
                    await db.commit()
                    await db.refresh(existing)
                    print(f"✅ User updated to SUPERADMIN: {email}")
                    print(f"   ID: {existing.id}")
                    return
            
            # Create new superadmin
            superadmin = User(
                email=email,
                hashed_password=hash_password(password),
                name=name,
                role=UserRole.SUPERADMIN,
                broker_id=None,
                is_active=True
            )
            
            db.add(superadmin)
            await db.commit()
            await db.refresh(superadmin)
            
            print(f"✅ Superadmin created successfully!")
            print(f"   ID: {superadmin.id}")
            print(f"   Email: {email}")
            print(f"   Name: {name}")
            print(f"   Role: SUPERADMIN")
            print(f"\n🔑 Login credentials:")
            print(f"   Email: {email}")
            print(f"   Password: {password}")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 create_superadmin_simple.py <email> <password> [name]")
        print("Example: python3 create_superadmin_simple.py admin@inmo.com admin123456 'Super Admin'")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Super Admin"
    
    print("=" * 60)
    print("🚀 CREATING SUPERADMIN")
    print("=" * 60)
    print()
    
    asyncio.run(create_superadmin(email, password, name))


