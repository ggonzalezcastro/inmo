"""
Script para crear un superusuario admin del sistema
Permite crear brokers y gestionar todo el sistema
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


async def create_superadmin(
    email: str,
    password: str,
    name: str = "Super Admin"
):
    """Create a superadmin user"""
    
    # Create database engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            # Check if superadmin already exists
            result = await db.execute(
                select(User).where(User.email == email)
            )
            existing_user = result.scalars().first()
            
            if existing_user:
                print(f"❌ User with email {email} already exists!")
                if existing_user.role == UserRole.SUPERADMIN:
                    print("✅ This user is already a SUPERADMIN")
                else:
                    print(f"⚠️  Current role: {existing_user.role.value}")
                    response = input("Do you want to update it to SUPERADMIN? (y/n): ")
                    if response.lower() == 'y':
                        existing_user.role = UserRole.SUPERADMIN
                        existing_user.hashed_password = hash_password(password)
                        existing_user.name = name
                        existing_user.broker_id = None  # Superadmin has no broker
                        await db.commit()
                        print(f"✅ User {email} updated to SUPERADMIN successfully!")
                    else:
                        print("Cancelled.")
                return
            
            # Check if any superadmin exists
            result = await db.execute(
                select(User).where(User.role == UserRole.SUPERADMIN)
            )
            existing_superadmin = result.scalars().first()
            
            if existing_superadmin:
                print(f"⚠️  A superadmin already exists: {existing_superadmin.email}")
                response = input("Do you want to create another superadmin anyway? (y/n): ")
                if response.lower() != 'y':
                    print("Cancelled.")
                    return
            
            # Create superadmin user
            hashed_pwd = hash_password(password)
            superadmin = User(
                email=email,
                hashed_password=hashed_pwd,
                name=name,
                role=UserRole.SUPERADMIN,
                broker_id=None,  # Superadmin has no broker
                is_active=True
            )
            
            db.add(superadmin)
            await db.commit()
            await db.refresh(superadmin)
            
            print(f"\n✅ Superadmin created successfully!")
            print(f"   Email: {email}")
            print(f"   Name: {name}")
            print(f"   Role: SUPERADMIN")
            print(f"   ID: {superadmin.id}")
            print(f"\n🔑 You can now login with this email and password")
            print(f"   This user can create brokers and manage the entire system")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error creating superadmin: {e}")
            raise
        finally:
            await engine.dispose()


def main():
    """Main function"""
    print("=" * 60)
    print("🚀 CREATE SUPERADMIN USER")
    print("=" * 60)
    print()
    
    # Get email
    email = input("Enter email for superadmin: ").strip()
    if not email:
        print("❌ Email is required!")
        return
    
    # Get password
    import getpass
    password = getpass.getpass("Enter password: ").strip()
    if not password:
        print("❌ Password is required!")
        return
    
    password_confirm = getpass.getpass("Confirm password: ").strip()
    if password != password_confirm:
        print("❌ Passwords do not match!")
        return
    
    # Get name (optional)
    name = input("Enter name (default: 'Super Admin'): ").strip()
    if not name:
        name = "Super Admin"
    
    print()
    print("Creating superadmin...")
    
    # Run async function
    asyncio.run(create_superadmin(email, password, name))


if __name__ == "__main__":
    main()


