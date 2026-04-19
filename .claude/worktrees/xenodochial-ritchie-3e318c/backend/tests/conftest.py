"""
Pytest configuration and fixtures for testing.

This file contains reusable fixtures for:
- Test database sessions
- Test client
- Authentication helpers
- Mock services
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.middleware.auth import create_access_token, hash_password
from app.models.user import User, UserRole
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON, String
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import now

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_postgres(type_, compiler, **kw):
    return "VARCHAR(36)"

@compiles(now, "sqlite")
def compile_now_sqlite(element, compiler, **kw):
    print("DEBUG: Compiling now() for SQLite")
    return "datetime('now')"


# Use SQLite for testing (in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create async test engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with overridden database dependency"""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Create sync test client for simpler tests"""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database"""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.ADMIN,
        broker_id=None,
        name="Test User"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for a test user"""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_gemini():
    """Mock LLM provider (facade) for testing without real API calls"""
    async def fake_generate_response(prompt):
        return "Mocked AI response for testing."
    async def fake_analyze(*args, **kwargs):
        return {"qualified": "maybe", "score_delta": 0}
    async def fake_build_prompt(*args, **kwargs):
        return ("System prompt", "Contents")
    async def fake_generate_with_tools(*args, **kwargs):
        return ("Mocked response", [])
    mock_provider = MagicMock()
    mock_provider.generate_response = AsyncMock(side_effect=fake_generate_response)
    mock_provider.analyze_lead_qualification = AsyncMock(side_effect=fake_analyze)
    mock_provider.build_llm_prompt = AsyncMock(side_effect=fake_build_prompt)
    mock_provider.generate_response_with_function_calling = AsyncMock(side_effect=fake_generate_with_tools)
    mock_provider.is_configured = True
    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        yield mock_provider


@pytest.fixture
def mock_redis():
    """Mock Redis for testing without real Redis connection"""
    with patch("redis.Redis.from_url") as mock_redis:
        mock_instance = MagicMock()
        mock_instance.ping.return_value = True
        mock_instance.zadd.return_value = 1
        mock_instance.zremrangebyscore.return_value = 0
        mock_instance.zcard.return_value = 1
        mock_instance.expire.return_value = True
        mock_instance.pipeline.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        mock_instance.execute.return_value = [1, 0, 1, True]
        mock_redis.return_value = mock_instance
        yield mock_instance
