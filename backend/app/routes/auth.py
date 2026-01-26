from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr
from datetime import timedelta


from app.database import get_db
from app.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)
from app.models.user import User, UserRole
from app.config import settings


router = APIRouter()


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    broker_name: str  # Se mantiene en el schema pero se mapea a 'name'


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
        name=user_data.broker_name,  # Mapear broker_name a name
        role=UserRole.AGENT,  # Usar el enum correcto
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create token with role and broker_id
    token_data = {
        "sub": str(new_user.id),
        "email": new_user.email
    }
    
    # Add role if available
    if hasattr(new_user, 'role') and new_user.role:
        token_data["role"] = new_user.role.value if hasattr(new_user.role, 'value') else str(new_user.role)
    
    # Add broker_id if available
    if hasattr(new_user, 'broker_id') and new_user.broker_id:
        token_data["broker_id"] = new_user.broker_id
    
    access_token = create_access_token(data=token_data)
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user"""
    import logging
    logger = logging.getLogger(__name__)
    
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


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user information"""
    
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

