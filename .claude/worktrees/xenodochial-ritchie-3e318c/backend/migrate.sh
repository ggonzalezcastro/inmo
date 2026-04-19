#!/bin/sh
set -e

echo "=== Resetting database ==="
python3 -c "
import os
from sqlalchemy import create_engine, text
raw_url = os.environ['DATABASE_URL']
url = raw_url.replace('postgresql+asyncpg://', 'postgresql://').replace('postgres://', 'postgresql://')
engine = create_engine(url)
with engine.begin() as conn:
    conn.execute(text('DROP SCHEMA public CASCADE'))
    conn.execute(text('CREATE SCHEMA public'))
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
print('Schema reset OK')
"

echo "=== Running migrations ==="
alembic upgrade heads

echo "=== Seeding data ==="
python3 -c "
import os, sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
raw_url = os.environ['DATABASE_URL']
url = raw_url.replace('postgresql+asyncpg://', 'postgresql://').replace('postgres://', 'postgresql://')
engine = create_engine(url)
Session = sessionmaker(bind=engine)
session = Session()

from app.models.broker import Broker
from app.models.user import User, UserRole
from app.middleware.auth import hash_password

broker = Broker(name='Demo Inmobiliaria')
session.add(broker)
session.flush()

admin = User(
    email='admin@demo.cl',
    hashed_password=hash_password('Admin1234!'),
    name='Admin Demo',
    role=UserRole.ADMIN,
    broker_id=broker.id,
    is_active=True,
)
session.add(admin)

agent = User(
    email='agente@demo.cl',
    hashed_password=hash_password('Agente1234!'),
    name='Agente Demo',
    role=UserRole.AGENT,
    broker_id=broker.id,
    is_active=True,
)
session.add(agent)
session.commit()
print(f'Seeded: broker={broker.id}, admin=admin@demo.cl, agent=agente@demo.cl')
session.close()
"

echo "=== Done ==="
