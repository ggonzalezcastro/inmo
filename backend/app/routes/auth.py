from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr, field_validator
from datetime import timedelta

from app.schemas.user import validate_password_strength
from app.database import get_db
from app.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)
from app.models.user import User, UserRole
from app.config import settings
from app.services.broker import BrokerInitService


router = APIRouter()


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    broker_name: str  # Se mantiene en el schema pero se mapea a 'name'

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "admin@inmobiliaria-activa.cl",
                "password": "Seguro123!",
                "broker_name": "Inmobiliaria Activa",
            }
        }
    }

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "admin@inmobiliaria-activa.cl",
                "password": "Seguro123!",
            }
        }
    }


class Token(BaseModel):
    access_token: str
    token_type: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }
    }


@router.post(
    "/register",
    response_model=Token,
    summary="Register a new broker",
    responses={
        200: {"description": "Broker created, returns JWT access token"},
        400: {"description": "Email already registered"},
        422: {"description": "Validation error (password too weak, invalid email)"},
    },
)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new broker account.

    Creates a user with role **ADMIN**, initialises a broker entity, and returns
    a signed JWT token ready for use in subsequent requests.

    **Password requirements:** min 8 chars, at least one digit and one special character.
    """
    
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
        name=user_data.broker_name,  # Mapear broker_name a name
        role=UserRole.AGENT,  # Temporal, se cambiará a ADMIN después
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Initialize broker and configurations automatically
    try:
        broker = await BrokerInitService.initialize_broker_for_user(
            db=db,
            user=new_user,
            broker_name=user_data.broker_name
        )
        logger.info(f"Broker initialized for user {new_user.email}: {broker.id if broker else 'None'}")
    except Exception as e:
        logger.error(f"Error initializing broker for user {new_user.email}: {e}")
        # Continue anyway - user is created but without broker config
        # They can configure it later
    
    # Refresh user to get updated broker_id and role after broker initialization
    await db.refresh(new_user)
    
    # Create token with role and broker_id (now updated)
    token_data = {
        "sub": str(new_user.id),
        "email": new_user.email
    }
    
    # Add role if available (should be ADMIN after initialization)
    if hasattr(new_user, 'role') and new_user.role:
        token_data["role"] = new_user.role.value if hasattr(new_user.role, 'value') else str(new_user.role)
    
    # Add broker_id if available (should be set after initialization)
    if hasattr(new_user, 'broker_id') and new_user.broker_id:
        token_data["broker_id"] = new_user.broker_id
    
    access_token = create_access_token(data=token_data)
    
    return {"access_token": access_token, "token_type": "bearer"}


import logging
logger = logging.getLogger(__name__)


@router.post(
    "/login",
    response_model=Token,
    summary="Login and obtain JWT token",
    responses={
        200: {"description": "Successful login, returns JWT access token"},
        401: {"description": "Invalid credentials"},
    },
)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email and password, receive a JWT Bearer token.

    The token expires after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60 min).
    Pass it as `Authorization: Bearer <token>` in all subsequent requests.
    """
    
    logger.info(f"Login attempt for email: {user_data.email}")
    
    # Find user
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalars().first()
    
    if not user:
        logger.warning(f"Login failed: User not found for email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    password_valid = verify_password(user_data.password, user.hashed_password)
    logger.info(f"Password verification result for {user_data.email}: {password_valid}")
    
    if not password_valid:
        logger.warning(f"Login failed: Invalid password for email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    logger.info(f"Login successful for user: {user_data.email} (ID: {user.id}, Role: {user.role})")
    
    # Create token with role and broker_id
    token_data = {
        "sub": str(user.id),
        "email": user.email
    }
    
    # Add role if available
    if hasattr(user, 'role') and user.role:
        token_data["role"] = user.role.value if hasattr(user.role, 'value') else str(user.role)
    
    # Add broker_id if available
    if hasattr(user, 'broker_id') and user.broker_id:
        token_data["broker_id"] = user.broker_id
    
    access_token = create_access_token(data=token_data)
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/me",
    summary="Get current user profile",
    responses={
        200: {
            "description": "Current user details",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "email": "admin@inmobiliaria-activa.cl",
                        "name": "Inmobiliaria Activa",
                        "role": "ADMIN",
                        "broker_id": 1,
                        "is_active": True,
                    }
                }
            },
        },
        401: {"description": "Invalid or expired token"},
    },
)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the profile of the currently authenticated user."""
    
    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found in token")
    
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get role value
    role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": role_value,
        "broker_id": user.broker_id,
        "is_active": user.is_active
    }

