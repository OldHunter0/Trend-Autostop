"""FastAPI dependencies for authentication and authorization."""
from typing import Optional
from datetime import datetime
from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole


# HTTP Bearer security scheme (for API access)
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated (optional).
    Supports both Bearer token and cookie-based auth.
    """
    token = None
    
    # First try Bearer token (API clients)
    if credentials:
        token = credentials.credentials
    # Then try cookie (web clients)
    elif access_token:
        token = access_token
    
    if not token:
        return None
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        return None
    
    # Check token type
    if payload.get("type") != "access":
        return None
    
    # Get user ID from token
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    
    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    # Check if user is active and not locked
    if not user.is_active:
        return None
    
    if user.is_locked():
        return None
    
    return user


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """Get current user (required - raises if not authenticated)."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user)
) -> User:
    """Get current active user with verified email."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    return user


async def get_current_verified_user(
    user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with verified email."""
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    return user


async def get_admin_user(
    user: User = Depends(get_current_active_user)
) -> User:
    """Get current user and verify admin role."""
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    # Check for forwarded headers (when behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


def get_user_agent(request: Request) -> str:
    """Get user agent from request."""
    return request.headers.get("User-Agent", "unknown")[:500]

