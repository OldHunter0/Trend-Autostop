"""API routes for position management."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.security import encrypt_api_key, decrypt_api_key
from app.models.position import PositionConfig, Position, OperationLog, APICredential
from app.schemas.position import (
    PositionConfigCreate,
    PositionConfigUpdate,
    PositionConfigResponse,
    PositionResponse,
    OperationLogResponse,
    APICredentialCreate,
    APICredentialResponse,
    DashboardStats,
    StopLossAdjustment
)
from app.services.exchange import ExchangeService
from app.services.supertrend import SuperTrendCalculator

router = APIRouter(prefix="/api", tags=["api"])


# ============ API Credentials ============

@router.post("/credentials", response_model=APICredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: APICredentialCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new API credential (encrypted storage)."""
    credential = APICredential(
        name=data.name,
        exchange=data.exchange,
        api_key_encrypted=encrypt_api_key(data.api_key),
        api_secret_encrypted=encrypt_api_key(data.api_secret),
        is_testnet=data.is_testnet
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential


@router.get("/credentials", response_model=List[APICredentialResponse])
async def list_credentials(db: AsyncSession = Depends(get_db)):
    """List all API credentials."""
    result = await db.execute(select(APICredential).order_by(desc(APICredential.created_at)))
    return result.scalars().all()


@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: int, db: AsyncSession = Depends(get_db)):
    """Delete API credential."""
    result = await db.execute(select(APICredential).where(APICredential.id == credential_id))
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    await db.delete(credential)
    await db.commit()
    return {"message": "Credential deleted"}


# ============ Position Configs ============

@router.post("/configs", response_model=PositionConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    data: PositionConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new position configuration."""
    # Verify credential exists
    result = await db.execute(select(APICredential).where(APICredential.id == data.credential_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Credential not found")
    
    config = PositionConfig(
        symbol=data.symbol,
        side=data.side,
        credential_id=data.credential_id,
        timeframe=data.timeframe,
        sl_offset=data.sl_offset,
        delay_bars=data.delay_bars,
        ema_len=data.ema_len,
        atr_len=data.atr_len,
        base_mult=data.base_mult,
        vol_lookback=data.vol_lookback,
        vol_power=data.vol_power,
        trend_lookback=data.trend_lookback,
        trend_impact=data.trend_impact,
        mult_min=data.mult_min,
        mult_max=data.mult_max,
        confirm_bars=data.confirm_bars,
        entry_bar_time=datetime.utcnow()
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    # Log creation
    log = OperationLog(
        config_id=config.id,
        symbol=config.symbol,
        action="create_config",
        message=f"Created config for {config.symbol} ({config.side})",
        success=True
    )
    db.add(log)
    await db.commit()
    
    return config


@router.get("/configs", response_model=List[PositionConfigResponse])
async def list_configs(db: AsyncSession = Depends(get_db)):
    """List all position configurations."""
    result = await db.execute(select(PositionConfig).order_by(desc(PositionConfig.created_at)))
    return result.scalars().all()


@router.get("/configs/{config_id}", response_model=PositionConfigResponse)
async def get_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """Get specific position configuration."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.patch("/configs/{config_id}", response_model=PositionConfigResponse)
async def update_config(
    config_id: int,
    data: PositionConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update position configuration."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    config.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(config)
    
    # Log update
    log = OperationLog(
        config_id=config.id,
        symbol=config.symbol,
        action="update_config",
        message=f"Updated config: {list(update_data.keys())}",
        success=True
    )
    db.add(log)
    await db.commit()
    
    return config


@router.delete("/configs/{config_id}")
async def delete_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """Delete position configuration."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    await db.delete(config)
    await db.commit()
    return {"message": "Config deleted"}


@router.post("/configs/{config_id}/pause")
async def pause_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """Pause position monitoring."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config.status = "paused"
    await db.commit()
    return {"message": "Config paused"}


@router.post("/configs/{config_id}/resume")
async def resume_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """Resume position monitoring."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config.status = "active"
    await db.commit()
    return {"message": "Config resumed"}


# ============ Positions ============

@router.get("/positions", response_model=List[PositionResponse])
async def list_positions(db: AsyncSession = Depends(get_db)):
    """List all position snapshots."""
    result = await db.execute(select(Position).order_by(desc(Position.updated_at)))
    return result.scalars().all()


@router.post("/configs/{config_id}/adjust-stop", response_model=PositionConfigResponse)
async def adjust_stop_loss(
    config_id: int,
    data: StopLossAdjustment,
    db: AsyncSession = Depends(get_db)
):
    """Manually adjust stop loss price."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Get credential
    cred_result = await db.execute(select(APICredential).where(APICredential.id == config.credential_id))
    credential = cred_result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    old_stop = config.current_stop_price
    
    try:
        # Create exchange service and update stop
        exchange = ExchangeService(
            exchange_id=credential.exchange,
            api_key=decrypt_api_key(credential.api_key_encrypted),
            api_secret=decrypt_api_key(credential.api_secret_encrypted),
            sandbox=credential.is_testnet
        )
        
        # Get current position size
        positions = await exchange.get_positions(config.symbol)
        position = next((p for p in positions if p.side == config.side), None)
        
        if position:
            await exchange.update_stop_loss(
                symbol=config.symbol,
                position_side=config.side,
                new_stop_price=data.new_stop_price,
                amount=position.size
            )
        
        await exchange.close()
        
        config.current_stop_price = data.new_stop_price
        await db.commit()
        await db.refresh(config)
        
        # Log adjustment
        log = OperationLog(
            config_id=config.id,
            symbol=config.symbol,
            action="manual_adjust",
            message=f"Manual stop adjustment",
            old_value=old_stop,
            new_value=data.new_stop_price,
            success=True
        )
        db.add(log)
        await db.commit()
        
    except Exception as e:
        log = OperationLog(
            config_id=config.id,
            symbol=config.symbol,
            action="manual_adjust",
            message=f"Failed to adjust stop",
            success=False,
            error_message=str(e)
        )
        db.add(log)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))
    
    return config


# ============ Logs ============

@router.get("/logs", response_model=List[OperationLogResponse])
async def list_logs(
    limit: int = 100,
    config_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    """List operation logs."""
    query = select(OperationLog).order_by(desc(OperationLog.created_at)).limit(limit)
    if config_id:
        query = query.where(OperationLog.config_id == config_id)
    result = await db.execute(query)
    return result.scalars().all()


# ============ Dashboard ============

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    configs_result = await db.execute(select(PositionConfig))
    configs = configs_result.scalars().all()
    
    positions_result = await db.execute(select(Position))
    positions = positions_result.scalars().all()
    
    active_count = sum(1 for c in configs if c.status == "active")
    paused_count = sum(1 for c in configs if c.status == "paused")
    total_pnl = sum(p.unrealized_pnl for p in positions)
    
    last_update = None
    if positions:
        last_update = max(p.updated_at for p in positions)
    
    return DashboardStats(
        total_positions=len(positions),
        active_tasks=active_count,
        paused_tasks=paused_count,
        total_unrealized_pnl=total_pnl,
        last_update=last_update
    )

