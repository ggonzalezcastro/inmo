"""
Broker users management routes
Endpoints for managing users within a broker
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator
from app.database import get_db
from app.schemas.user import validate_password_strength
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.models.user import User, UserRole
from passlib.context import CryptContext
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "agent"  # "admin" or "agent"
    broker_id: Optional[int] = None  # Optional: required for superadmin, ignored for admin (uses their broker_id)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/users")
async def get_broker_users(
    broker_id: Optional[int] = Query(None, description="Filter by broker ID (superadmin only)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List users of the broker"""
    
    user_role = current_user.get("role", "").upper()
    if user_role not in ["ADMIN", "SUPERADMIN"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver usuarios")
    
    # Determine which broker_id to use
    if user_role == "SUPERADMIN":
        # Superadmin can filter by broker_id or see all users
        if broker_id:
            query = select(User).where(User.broker_id == broker_id)
        else:
            # Show all users if no broker_id specified
            query = select(User)
    else:
        # Admin only sees users from their broker
        user_broker_id = current_user.get("broker_id")
        if not user_broker_id:
            raise HTTPException(status_code=404, detail="User does not belong to a broker")
        query = select(User).where(User.broker_id == user_broker_id)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value if hasattr(user.role, 'value') else user.role,
                "broker_id": user.broker_id,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
    }


@router.post("/users")
async def create_broker_user(
    user_data: CreateUserRequest,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user for the broker (admin or superadmin)"""
    
    user_role = current_user.get("role", "").upper()
    
    # Determine broker_id based on role
    if user_role == "SUPERADMIN":
        # Superadmin must specify broker_id
        if not user_data.broker_id:
            raise HTTPException(
                status_code=400, 
                detail="broker_id es requerido para superadmin. Debe especificar el broker al cual pertenecerá el usuario."
            )
        broker_id = user_data.broker_id
        
        # Verify broker exists
        from app.models.broker import Broker
        broker_result = await db.execute(
            select(Broker).where(Broker.id == broker_id)
        )
        broker = broker_result.scalars().first()
        if not broker:
            raise HTTPException(status_code=404, detail="Broker no encontrado")
    else:
        # Admin uses their own broker_id
        broker_id = current_user.get("broker_id")
        if not broker_id:
            raise HTTPException(status_code=404, detail="User does not belong to a broker")
    
    # Validate role (superadmin cannot be created via this endpoint)
    if user_data.role not in ["admin", "agent"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Debe ser 'admin' o 'agent'")
    
    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="El email ya está en uso")
    
    # Create user
    hashed_password = pwd_context.hash(user_data.password)
    
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        name=user_data.name,
        role=UserRole[user_data.role.upper()],
        broker_id=broker_id,
        is_active=True
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"User created: {user.id} - {user.email} in broker {broker_id} by {user_role} {current_user.get('email')}")
    
    return {
        "message": "Usuario creado exitosamente",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "broker_id": user.broker_id
        }
    }


@router.put("/users/{user_id}")
async def update_broker_user(
    user_id: int,
    updates: UpdateUserRequest,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a broker user (admin or superadmin)"""
    
    user_role = current_user.get("role", "").upper()
    
    # Get user
    if user_role == "SUPERADMIN":
        # Superadmin can update any user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
    else:
        # Admin can only update users from their broker
        broker_id = current_user.get("broker_id")
        if not broker_id:
            raise HTTPException(status_code=404, detail="User does not belong to a broker")
        result = await db.execute(
            select(User).where(User.id == user_id, User.broker_id == broker_id)
        )
    
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Don't allow updating to superadmin role
    update_data = updates.model_dump(exclude_unset=True)
    if "role" in update_data:
        if update_data["role"] not in ["admin", "agent"]:
            raise HTTPException(status_code=400, detail="Rol inválido. Solo se permiten roles 'admin' o 'agent'")
        user.role = UserRole[update_data["role"].upper()]
        del update_data["role"]
    
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "Usuario actualizado exitosamente",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "broker_id": user.broker_id,
            "is_active": user.is_active
        }
    }


@router.delete("/users/{user_id}")
async def delete_broker_user(
    user_id: int,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a broker user (admin or superadmin)"""
    
    user_role = current_user.get("role", "").upper()
    
    # Get user
    if user_role == "SUPERADMIN":
        # Superadmin can deactivate any user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
    else:
        # Admin can only deactivate users from their broker
        broker_id = current_user.get("broker_id")
        if not broker_id:
            raise HTTPException(status_code=404, detail="User does not belong to a broker")
        result = await db.execute(
            select(User).where(User.id == user_id, User.broker_id == broker_id)
        )
    
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Don't allow deleting yourself
    if user.id == current_user.get("id"):
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")
    
    # Don't allow deactivating superadmin users (unless you're superadmin)
    if user.role == UserRole.SUPERADMIN and user_role != "SUPERADMIN":
        raise HTTPException(status_code=403, detail="No puedes desactivar usuarios superadmin")
    
    # Deactivate instead of delete
    user.is_active = False
    await db.commit()
    
    logger.info(f"User deactivated: {user.id} - {user.email} by {user_role} {current_user.get('email')}")
    
    return {
        "message": "Usuario desactivado exitosamente"
    }

