from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config import settings
from app.database import get_db
from app.models.user import User


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


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode a JWT and return the payload dict, or None if invalid/expired.
    Used for non-HTTP contexts such as WebSocket authentication.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get current authenticated user from JWT token and load from DB"""
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
    
    # ── Impersonation mode ────────────────────────────────────────────────────
    # When a superadmin impersonates a broker, the JWT carries:
    #   impersonating: true, role: "ADMIN", broker_id: <target>, original_role: "SUPERADMIN"
    # In this case we use the JWT claims directly (role + broker_id) instead of
    # reloading from DB, so the caller sees the broker-scoped identity.
    # The original user's role is always verified against the database.
    if payload.get("impersonating"):
        original_role_claim = payload.get("original_role")
        if not original_role_claim:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Impersonation token missing original_role claim",
            )

        # Verify the original user is actually a SUPERADMIN in the database
        try:
            orig_result = await db.execute(
                select(User).where(User.id == int(user_id))
            )
        except (ValueError, TypeError):
            orig_result = await db.execute(
                select(User).where(User.email == user_id)
            )
        original_user = orig_result.scalars().first()

        if not original_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Impersonating user not found",
            )

        orig_role_value = original_user.role.value if hasattr(original_user.role, 'value') else str(original_user.role)
        if (orig_role_value or "").upper() != "SUPERADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can impersonate other users",
            )

        # Validate that the target broker still exists and is active (issue #6)
        target_broker_id = payload.get("broker_id")
        if target_broker_id:
            from app.models.broker import Broker
            broker_result = await db.execute(
                select(Broker).where(Broker.id == target_broker_id)
            )
            target_broker = broker_result.scalars().first()
            if not target_broker or not target_broker.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Target broker is inactive or does not exist",
                )

        jwt_role = (payload.get("role") or "AGENT").upper()
        return {
            "user_id": user_id,
            "role": jwt_role,
            "broker_id": payload.get("broker_id"),
            "email": payload.get("email", ""),
            "payload": payload,
            "impersonating": True,
            "original_role": orig_role_value.upper(),
        }

    # ── Normal mode ───────────────────────────────────────────────────────────
    # Load user from DB to get current role and broker_id
    # Support both integer ID and email as sub (legacy tokens used email)
    try:
        result = await db.execute(
            select(User).where(User.id == int(user_id))
        )
    except (ValueError, TypeError):
        result = await db.execute(
            select(User).where(User.email == user_id)
        )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Get role value and normalize to uppercase
    role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
    role_normalized = role_value.upper() if role_value else ""

    return {
        "user_id": user_id,
        "role": role_normalized,  # Always return uppercase
        "broker_id": user.broker_id,
        "email": user.email,
        "payload": payload
    }

