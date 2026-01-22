"""
Permission middleware for role-based access control
"""
from functools import wraps
from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.middleware.auth import get_current_user
from app.database import get_db

class Permissions:
    """Decorators and helpers for verifying permissions"""
    
    @staticmethod
    async def require_superadmin(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        """Require superadmin role only"""
        role = current_user.get("role", "").upper()
        if role != "SUPERADMIN":
            raise HTTPException(
                status_code=403,
                detail="Se requiere rol de superadmin"
            )
        return current_user
    
    @staticmethod
    async def require_admin(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        """Require admin or superadmin role"""
        role = current_user.get("role", "").upper()
        if role not in ["ADMIN", "SUPERADMIN"]:
            raise HTTPException(
                status_code=403,
                detail="Se requiere rol de administrador"
            )
        return current_user
    
    @staticmethod
    async def require_same_broker(
        broker_id: int,
        current_user: dict = Depends(get_current_user)
    ) -> bool:
        """Verify that user belongs to the broker or is superadmin"""
        role = current_user.get("role", "").upper()
        if role == "SUPERADMIN":
            return True
        
        if current_user.get("broker_id") != broker_id:
            raise HTTPException(
                status_code=403,
                detail="No tienes acceso a este broker"
            )
        return True
    
    @staticmethod
    async def get_user_broker_id(
        current_user: dict = Depends(get_current_user)
    ) -> Optional[int]:
        """Get broker_id from current user"""
        return current_user.get("broker_id")
    
    @staticmethod
    async def can_access_lead(
        lead_broker_id: Optional[int],
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> bool:
        """Check if user can access a lead"""
        role = current_user.get("role", "").upper()
        # Superadmin can access all
        if role == "SUPERADMIN":
            return True
        
        user_broker_id = current_user.get("broker_id")
        
        # If lead has no broker_id, only superadmin can access (or migrate)
        if lead_broker_id is None:
            return role == "SUPERADMIN"
        
        # User must belong to same broker
        return user_broker_id == lead_broker_id


