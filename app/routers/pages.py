"""Page routes for web interface."""
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.position import PositionConfig, Position, OperationLog, APICredential

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Dashboard page."""
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
async def positions_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Positions management page."""
    configs_result = await db.execute(
        select(PositionConfig).order_by(desc(PositionConfig.created_at))
    )
    configs = configs_result.scalars().all()
    
    credentials_result = await db.execute(select(APICredential))
    credentials = credentials_result.scalars().all()
    
    return templates.TemplateResponse("positions.html", {
        "request": request,
        "configs": configs,
        "credentials": credentials,
        "timeframes": ["10min", "15min", "30min", "1h", "4h"]
    })


@router.get("/settings")
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Settings page for API credentials."""
    credentials_result = await db.execute(
        select(APICredential).order_by(desc(APICredential.created_at))
    )
    credentials = credentials_result.scalars().all()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "credentials": credentials
    })


@router.get("/logs")
async def logs_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Logs page."""
    logs_result = await db.execute(
        select(OperationLog).order_by(desc(OperationLog.created_at)).limit(200)
    )
    logs = logs_result.scalars().all()
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs
    })

