# AI Lead Agent Pro - DEEP DIVE TASKS
## Detailed Code Examples & Implementation Specifics

---

## BLOCK 1: Backend Infrastructure (Week 1-2)

### Task 1.1 DEEP DIVE: Project Setup & Docker

#### Step 1: Create requirements.txt (EXACT versions)

```txt
# Web Framework
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6

# Database
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
alembic==1.13.0

# Data Validation
pydantic==2.5.0
pydantic-settings==2.1.0

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.1

# Job Queue
celery==5.3.4
redis==5.0.1

# HTTP Client
httpx==0.25.2

# AI/ML
openai==1.3.0

# Telegram
python-telegram-bot==20.3

# Utilities
python-dotenv==1.0.0
pydantic-extra-types==2.1.0

# Logging
python-json-logger==2.0.7

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2
```

#### Step 2: Create .env.example

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/lead_agent

# Redis
REDIS_URL=redis://redis:6379/0

# JWT & Security
SECRET_KEY=your-secret-key-here-min-32-chars-please
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo

# Telegram
TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhooks/telegram
TELEGRAM_WEBHOOK_SECRET=your-webhook-secret

# Environment
DEBUG=False
ENVIRONMENT=development

# Database Pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

#### Step 3: Create docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: lead_user
      POSTGRES_PASSWORD: lead_pass_123
      POSTGRES_DB: lead_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lead_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://lead_user:lead_pass_123@db:5432/lead_agent
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.celery_app worker --loglevel=info
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://lead_user:lead_pass_123@db:5432/lead_agent
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
      - backend

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.celery_app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://lead_user:lead_pass_123@db:5432/lead_agent
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  redis_data:
```

#### Step 4: Create backend/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Default command (override in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 5: Create project structure script

```bash
#!/bin/bash

mkdir -p backend/app/{models,schemas,routes,services,tasks,middleware,utils}
mkdir -p backend/migrations/versions
mkdir -p backend/tests
mkdir -p frontend/src/{components,pages,services,hooks,store}

# Backend files
touch backend/app/__init__.py
touch backend/app/main.py
touch backend/app/config.py
touch backend/app/database.py
touch backend/app/celery_app.py
touch backend/app/models/__init__.py
touch backend/app/models/base.py
touch backend/app/models/lead.py
touch backend/app/schemas/__init__.py
touch backend/app/routes/__init__.py
touch backend/app/services/__init__.py
touch backend/app/tasks/__init__.py
touch backend/tests/__init__.py

touch backend/.env
touch backend/.gitignore
touch backend/Dockerfile
```

---

### Task 1.2 DEEP DIVE: PostgreSQL & SQLAlchemy

#### Step 1: Create backend/app/database.py

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base
from app.config import settings

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base for all models
Base = declarative_base()

# Dependency for FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency injection"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Initialize database
async def init_db():
    """Create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Close database connections"""
    await engine.dispose()
```

#### Step 2: Create backend/app/models/base.py

```python
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.declarative import declared_attr

Base = declarative_base()

class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps"""
    
    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
        )

class IdMixin:
    """Mixin that adds an id primary key"""
    
    @declared_attr
    def id(cls):
        return Column(Integer, primary_key=True, index=True)
```

#### Step 3: Create backend/app/models/lead.py

```python
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, IdMixin

class LeadStatus(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CONVERTED = "converted"
    LOST = "lost"

class Lead(Base, IdMixin, TimestampMixin):
    """Lead model for storing prospect information"""
    
    __tablename__ = "leads"
    
    # Basic info
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Scoring & Status
    status = Column(
        String(20),
        default=LeadStatus.COLD,
        nullable=False,
        index=True
    )
    lead_score = Column(Float, default=0.0, nullable=False, index=True)
    lead_score_components = Column(
        JSON,
        default={"base": 0, "behavior": 0, "engagement": 0},
        nullable=False
    )
    
    # Contact tracking
    last_contacted = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Metadata
    tags = Column(JSON, default=[], nullable=False)  # ["inmobiliario", "activo"]
    metadata = Column(JSON, default={}, nullable=False)  # {budget: "150k", timeline: "30 dias"}
    
    # Relationships
    telegram_messages = relationship(
        "TelegramMessage",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    activities = relationship(
        "ActivityLog",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    
    # Indices
    __table_args__ = (
        Index('idx_status_score', 'status', 'lead_score'),
        Index('idx_phone', 'phone'),
        UniqueConstraint('phone', name='uq_phone'),
    )
    
    def __repr__(self):
        return f"<Lead id={self.id} phone={self.phone} status={self.status}>"
```

#### Step 4: Create backend/app/models/telegram_message.py

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import Base, IdMixin

class MessageDirection(str, Enum):
    INBOUND = "in"
    OUTBOUND = "out"

class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class TelegramMessage(Base, IdMixin):
    """Telegram message history"""
    
    __tablename__ = "telegram_messages"
    
    # Foreign key
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    
    # Telegram identifiers
    telegram_user_id = Column(Integer, nullable=False, index=True)
    telegram_username = Column(String(100), nullable=True)
    telegram_message_id = Column(String(100), nullable=True, unique=True)
    
    # Message data
    message_text = Column(Text, nullable=False)
    direction = Column(
        SQLEnum(MessageDirection),
        default=MessageDirection.OUTBOUND,
        nullable=False
    )
    status = Column(
        SQLEnum(MessageStatus),
        default=MessageStatus.SENT,
        nullable=False
    )
    
    # AI flag
    ai_response_used = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    
    # Relationship
    lead = relationship("Lead", back_populates="telegram_messages")
    
    def __repr__(self):
        return f"<TelegramMessage id={self.id} lead_id={self.lead_id} direction={self.direction}>"
```

#### Step 5: Create backend/app/models/activity_log.py

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin

class ActivityLog(Base, IdMixin):
    """Track all lead activities"""
    
    __tablename__ = "activity_log"
    
    # Foreign key
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Action type
    action_type = Column(
        String(50),  # message, call, score_update, status_change
        nullable=False,
        index=True
    )
    
    # Details as JSON
    details = Column(JSON, default={}, nullable=False)
    
    # Timestamp
    timestamp = Column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
        index=True
    )
    
    # Relationship
    lead = relationship("Lead", back_populates="activities")
    
    def __repr__(self):
        return f"<ActivityLog id={self.id} lead_id={self.lead_id} action={self.action_type}>"
```

#### Step 6: Create backend/app/config.py

```python
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/lead_agent"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT & Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-min-32-chars")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS: int = 150
    OPENAI_TEMPERATURE: float = 0.7
    
    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Environment
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

#### Step 7: Create Alembic migration script

```bash
cd backend
alembic init migrations
```

Edit `backend/alembic/env.py`:

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from app.database import Base
from app.models import *  # Import all models

config = context.config

fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online() -> None:
    from app.config import settings
    
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

Run first migration:

```bash
alembic revision --autogenerate -m "Initial migration: create leads, messages, activity tables"
alembic upgrade head
```

---

### Task 1.3 DEEP DIVE: FastAPI & Authentication

#### Step 1: Create backend/app/main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging

from app.database import init_db, close_db
from app.config import settings
from app.routes import health, auth, leads
from app.celery_app import celery_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    await init_db()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()

# Create FastAPI app
app = FastAPI(
    title="AI Lead Agent Pro",
    description="Real estate lead management with AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["localhost:5173", "localhost:3000", "127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", settings.ENVIRONMENT == "production"]
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "AI Lead Agent Pro API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Health check
@app.get("/health")
async def health_check():
    from app.database import engine
    from redis import Redis
    
    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Check Redis
    try:
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "ok" and redis_status == "ok" else "degraded",
        "database": db_status,
        "redis": redis_status,
    }

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["leads"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

#### Step 2: Create backend/app/middleware/auth.py

```python
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT config
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security)
) -> dict:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return {"user_id": user_id, "payload": payload}
```

#### Step 3: Create backend/app/routes/auth.py

```python
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr
from datetime import timedelta

from app.database import get_db
from app.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token
)
from app.models.user import User
from app.config import settings

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    broker_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", response_model=Token)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register new broker"""
    
    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        broker_name=user_data.broker_name,
        role="broker"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create token
    access_token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user"""
    
    # Find user
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalars().first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
```

#### Step 4: Create backend/app/routes/health.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

router = APIRouter()

@router.get("/")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        result = await db.execute("SELECT 1")
        db_ok = result.scalar() == 1
    except Exception as e:
        db_ok = False
    
    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database": "connected" if db_ok else "error"
    }
```

---

## BLOCK 2: Lead Management (Week 2-3)

### Task 2.1 DEEP DIVE: Lead CRUD Endpoints

#### Step 1: Create backend/app/schemas/lead.py

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

class LeadStatusEnum(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CONVERTED = "converted"
    LOST = "lost"

class LeadBase(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    tags: List[str] = []
    metadata: dict = {}

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[LeadStatusEnum] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None

class LeadResponse(LeadBase):
    id: int
    status: LeadStatusEnum
    lead_score: float
    last_contacted: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class LeadDetailResponse(LeadResponse):
    lead_score_components: dict
    recent_activities: List[dict] = []
```

#### Step 2: Create backend/app/services/lead_service.py

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Tuple
import re

from app.models.lead import Lead, LeadStatus
from app.schemas.lead import LeadCreate, LeadUpdate

class LeadService:
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normalize phone to international format
        Examples:
          912345678 → +56912345678
          +56912345678 → +56912345678
          56912345678 → +56912345678
        """
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # If starts with 56, add +
        if digits.startswith('56'):
            return f"+{digits}"
        
        # If Chilean number without country code
        if len(digits) == 9 and digits.startswith('9'):
            return f"+56{digits}"
        
        # Add + if not present
        if not digits.startswith('+'):
            return f"+{digits}"
        
        return digits
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """Validate phone number"""
        normalized = LeadService.normalize_phone(phone)
        digits = re.sub(r'\D', '', normalized)
        
        if len(digits) < 10:
            return False, "Phone must have at least 10 digits"
        
        if len(digits) > 15:
            return False, "Phone is too long"
        
        return True, normalized
    
    @staticmethod
    async def create_lead(
        db: AsyncSession,
        lead_data: LeadCreate
    ) -> Lead:
        """Create a new lead"""
        
        # Validate and normalize phone
        is_valid, phone = LeadService.validate_phone(lead_data.phone)
        if not is_valid:
            raise ValueError(phone)
        
        # Check for duplicate
        result = await db.execute(
            select(Lead).where(Lead.phone == phone)
        )
        existing = result.scalars().first()
        if existing:
            raise ValueError(f"Lead with phone {phone} already exists")
        
        # Create lead
        lead = Lead(
            phone=phone,
            name=lead_data.name,
            email=lead_data.email,
            tags=lead_data.tags,
            metadata=lead_data.metadata,
            status=LeadStatus.COLD,
            lead_score=0.0
        )
        
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def get_leads(
        db: AsyncSession,
        status: Optional[str] = None,
        min_score: float = 0,
        max_score: float = 100,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Lead], int]:
        """Get leads with filters"""
        
        filters = []
        
        # Status filter
        if status:
            statuses = status.split(',')
            filters.append(Lead.status.in_(statuses))
        
        # Score range filter
        filters.append(and_(Lead.lead_score >= min_score, Lead.lead_score <= max_score))
        
        # Search filter (name or phone)
        if search:
            search_term = f"%{search}%"
            filters.append(
                or_(
                    Lead.name.ilike(search_term),
                    Lead.phone.ilike(search_term)
                )
            )
        
        # Get total count
        count_query = select(func.count(Lead.id))
        if filters:
            count_query = count_query.where(and_(*filters))
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Get leads
        query = select(Lead)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(Lead.lead_score.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        leads = result.scalars().all()
        
        return leads, total_count
    
    @staticmethod
    async def get_lead(db: AsyncSession, lead_id: int) -> Optional[Lead]:
        """Get single lead"""
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        return result.scalars().first()
    
    @staticmethod
    async def update_lead(
        db: AsyncSession,
        lead_id: int,
        lead_data: LeadUpdate
    ) -> Lead:
        """Update lead"""
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # Update fields
        update_data = lead_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(lead, field, value)
        
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def delete_lead(db: AsyncSession, lead_id: int) -> bool:
        """Soft delete lead"""
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # In real implementation, add deleted_at timestamp
        await db.delete(lead)
        await db.commit()
        
        return True
```

#### Step 3: Create backend/app/routes/leads.py

```python
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import csv
import io

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.lead_service import LeadService
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse, LeadDetailResponse

router = APIRouter()

@router.get("", response_model=dict)
async def list_leads(
    status: str = "",
    min_score: float = 0,
    max_score: float = 100,
    search: str = "",
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all leads with filters"""
    try:
        leads, total = await LeadService.get_leads(
            db,
            status=status or None,
            min_score=min_score,
            max_score=max_score,
            search=search or None,
            skip=skip,
            limit=min(limit, 200)  # Max 200 per request
        )
        
        return {
            "data": [LeadResponse.from_orm(lead).dict() for lead in leads],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single lead"""
    lead = await LeadService.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return LeadDetailResponse.from_orm(lead)

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new lead"""
    try:
        lead = await LeadService.create_lead(db, lead_data)
        return LeadResponse.from_orm(lead)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    lead_data: LeadUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update lead"""
    try:
        lead = await LeadService.update_lead(db, lead_id, lead_data)
        return LeadResponse.from_orm(lead)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete lead"""
    try:
        await LeadService.delete_lead(db, lead_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/bulk-import")
async def bulk_import_leads(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import leads from CSV"""
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")
    
    contents = await file.read()
    reader = csv.DictReader(io.StringIO(contents.decode()))
    
    imported = 0
    duplicates = 0
    invalid = 0
    
    for row in reader:
        try:
            phone = row.get('phone', '').strip()
            name = row.get('name', '').strip()
            email = row.get('email', '').strip() or None
            tags_str = row.get('tags', '').strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            lead_data = LeadCreate(
                phone=phone,
                name=name or None,
                email=email,
                tags=tags
            )
            
            await LeadService.create_lead(db, lead_data)
            imported += 1
        except ValueError:
            duplicates += 1
        except Exception:
            invalid += 1
    
    return {
        "imported": imported,
        "duplicates": duplicates,
        "invalid": invalid
    }
```

---

Continuaremos con **BLOCK 3 (Telegram Bot), BLOCK 4 (Scoring), BLOCK 5 (Frontend)** en el siguiente mensaje.

¿Necesitas que continúe con los detalles profundos del Telegram Bot ahora o prefieres revisar estos primero?