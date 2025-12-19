"""Page routes for web interface."""
from typing import Optional
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.models.position import PositionConfig, Position, OperationLog, APICredential
from app.models.user import User

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


# ============ Auth Pages ============

@router.get("/auth/login")
async def login_page(
    request: Request,
    message: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Login page."""
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "message": message,
        "error": error
    })


@router.get("/auth/register")
async def register_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Register page."""
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {
        "request": request
    })


@router.get("/auth/forgot-password")
async def forgot_password_page(request: Request):
    """Forgot password page."""
    return templates.TemplateResponse("forgot_password.html", {
        "request": request
    })


@router.get("/auth/reset-password")
async def reset_password_page(
    request: Request,
    token: Optional[str] = Query(None),
    error: Optional[str] = Query(None)
):
    """Reset password page."""
    if not token:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": "无效的重置链接"
        })
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "error": error
    })


@router.get("/auth/verify-email")
async def verify_email_page(
    request: Request,
    token: Optional[str] = Query(None),
    success: Optional[str] = Query(None),
    error: Optional[str] = Query(None)
):
    """Email verification page."""
    return templates.TemplateResponse("verify_email.html", {
        "request": request,
        "token": token,
        "success": success == "1",
        "error": error
    })


# ============ Protected Pages ============


@router.get("/")
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Dashboard page."""
    # Redirect to login if not authenticated
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    configs_result = await db.execute(
        select(PositionConfig).order_by(desc(PositionConfig.created_at))
    )
    configs = configs_result.scalars().all()
    
    positions_result = await db.execute(select(Position))
    positions = positions_result.scalars().all()
    
    logs_result = await db.execute(
        select(OperationLog).order_by(desc(OperationLog.created_at)).limit(20)
    )
    logs = logs_result.scalars().all()
    
    credentials_result = await db.execute(select(APICredential))
    credentials = credentials_result.scalars().all()
    
    # Calculate stats
    active_count = sum(1 for c in configs if c.status == "active")
    paused_count = sum(1 for c in configs if c.status == "paused")
    total_pnl = sum(p.unrealized_pnl for p in positions)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "configs": configs,
        "positions": positions,
        "logs": logs,
        "credentials": credentials,
        "stats": {
            "total_positions": len(positions),
            "active_tasks": active_count,
            "paused_tasks": paused_count,
            "total_pnl": total_pnl
        }
    })


@router.get("/positions")
async def positions_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Positions management page."""
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    configs_result = await db.execute(
        select(PositionConfig).order_by(desc(PositionConfig.created_at))
    )
    configs = configs_result.scalars().all()
    
    credentials_result = await db.execute(select(APICredential))
    credentials = credentials_result.scalars().all()
    
    return templates.TemplateResponse("positions.html", {
        "request": request,
        "user": user,
        "configs": configs,
        "credentials": credentials,
        "timeframes": ["10min", "15min", "30min", "1h", "4h"]
    })


@router.get("/settings")
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Settings page for API credentials."""
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    credentials_result = await db.execute(
        select(APICredential).order_by(desc(APICredential.created_at))
    )
    credentials = credentials_result.scalars().all()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "credentials": credentials
    })


@router.get("/logs")
async def logs_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Logs page."""
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    logs_result = await db.execute(
        select(OperationLog).order_by(desc(OperationLog.created_at)).limit(200)
    )
    logs = logs_result.scalars().all()
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "user": user,
        "logs": logs
    })


@router.get("/strategies")
async def strategies_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Strategies page - shows available trading strategies."""
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    return templates.TemplateResponse("strategies.html", {
        "request": request,
        "user": user
    })


# ============ Admin Pages ============

@router.get("/admin")
async def admin_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Admin dashboard page."""
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # Check if user is admin
    if not user.is_admin():
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user
    })

