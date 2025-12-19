"""Admin API routes."""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.models.user import User, AuditLog, UserRole
from app.models.position import APICredential, PositionConfig, OperationLog
from app.schemas.auth import UserListItem, UserUpdate, AuditLogResponse, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============ User Management ============

@router.get("/users", response_model=List[UserListItem])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    # Get users
    result = await db.execute(
        select(User)
        .order_by(desc(User.created_at))
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    
    # Get credential counts per user (future: link credentials to users)
    # For now, return users without credential counts since credentials aren't user-linked yet
    user_list = []
    for user in users:
        user_list.append(UserListItem(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            is_email_verified=user.is_email_verified,
            has_api_credentials=False,  # TODO: Implement when credentials are linked to users
            credentials_count=0,
            last_login_at=user.last_login_at,
            created_at=user.created_at
        ))
    
    return user_list


@router.get("/users/{user_id}", response_model=UserListItem)
async def get_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific user details (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserListItem(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        has_api_credentials=False,
        credentials_count=0,
        last_login_at=user.last_login_at,
        created_at=user.created_at
    )


@router.patch("/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from disabling themselves
    if user.id == admin.id and data.is_active is False:
        raise HTTPException(
            status_code=400,
            detail="Cannot disable your own account"
        )
    
    # Prevent admin from removing their own admin role
    if user.id == admin.id and data.role == UserRole.USER.value:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove your own admin role"
        )
    
    # Update fields
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role is not None:
        user.role = data.role
    
    await db.commit()
    
    return MessageResponse(message=f"User {user.email} updated successfully")


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user (admin only)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    
    return MessageResponse(message=f"User {user.email} deleted successfully")


# ============ Audit Logs ============

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List audit logs (admin only)."""
    query = select(AuditLog).order_by(desc(AuditLog.created_at))
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    
    return result.scalars().all()


# ============ Dashboard Stats ============

@router.get("/stats")
async def get_admin_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics."""
    # User counts
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar()
    
    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active_users_result.scalar()
    
    verified_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_email_verified == True)
    )
    verified_users = verified_users_result.scalar()
    
    # Credential and config counts
    credentials_result = await db.execute(select(func.count(APICredential.id)))
    total_credentials = credentials_result.scalar()
    
    configs_result = await db.execute(select(func.count(PositionConfig.id)))
    total_configs = configs_result.scalar()
    
    active_configs_result = await db.execute(
        select(func.count(PositionConfig.id)).where(PositionConfig.status == "active")
    )
    active_configs = active_configs_result.scalar()
    
    # Recent errors
    errors_result = await db.execute(
        select(func.count(OperationLog.id))
        .where(OperationLog.success == False)
    )
    total_errors = errors_result.scalar()
    
    # Recent activity (last 24 hours)
    from datetime import timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    recent_logins_result = await db.execute(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == "login")
        .where(AuditLog.created_at >= yesterday)
    )
    recent_logins = recent_logins_result.scalar()
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "verified": verified_users
        },
        "trading": {
            "total_credentials": total_credentials,
            "total_configs": total_configs,
            "active_configs": active_configs
        },
        "health": {
            "total_errors": total_errors,
            "recent_logins_24h": recent_logins
        }
    }


# ============ Strategy Overview ============

@router.get("/strategies/overview")
async def get_strategies_overview(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get overview of all running strategies (admin only)."""
    # Get all configs with recent activity
    configs_result = await db.execute(
        select(PositionConfig).order_by(desc(PositionConfig.updated_at))
    )
    configs = configs_result.scalars().all()
    
    overview = {
        "total_configs": len(configs),
        "active": sum(1 for c in configs if c.status == "active"),
        "paused": sum(1 for c in configs if c.status == "paused"),
        "stopped": sum(1 for c in configs if c.status == "stopped"),
        "configs": [
            {
                "id": c.id,
                "symbol": c.symbol,
                "side": c.side,
                "status": c.status,
                "timeframe": c.timeframe,
                "current_stop": c.current_stop_price,
                "last_checked": c.last_checked_at.isoformat() if c.last_checked_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None
            }
            for c in configs[:50]  # Limit to 50 most recent
        ]
    }
    
    return overview

