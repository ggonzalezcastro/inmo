#!/bin/bash
# Quick script to create superadmin with default credentials

cd "$(dirname "$0")/.."

EMAIL="${1:-superadmin@inmo.com}"
PASSWORD="${2:-admin123456}"
NAME="${3:-Super Admin}"

echo "Creating superadmin..."
echo "Email: $EMAIL"
echo "Name: $NAME"
echo ""

python3 -c "
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').absolute()))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from app.models.user import User, UserRole
from app.middleware.auth import hash_password
from app.config import settings

async def create():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == '$EMAIL'))
        existing = result.scalars().first()
        
        if existing:
            if existing.role == UserRole.SUPERADMIN:
                print('✅ Superadmin already exists!')
                return
            existing.role = UserRole.SUPERADMIN
            existing.hashed_password = hash_password('$PASSWORD')
            existing.name = '$NAME'
            existing.broker_id = None
            await db.commit()
            print('✅ User updated to SUPERADMIN')
        else:
            superadmin = User(
                email='$EMAIL',
                hashed_password=hash_password('$PASSWORD'),
                name='$NAME',
                role=UserRole.SUPERADMIN,
                broker_id=None,
                is_active=True
            )
            db.add(superadmin)
            await db.commit()
            await db.refresh(superadmin)
            print('✅ Superadmin created successfully!')
            print(f'   ID: {superadmin.id}')
            print(f'   Email: $EMAIL')
            print(f'   Role: SUPERADMIN')
        
        await engine.dispose()

asyncio.run(create())
"

echo ""
echo "✅ Done! You can now login with:"
echo "   Email: $EMAIL"
echo "   Password: $PASSWORD"


