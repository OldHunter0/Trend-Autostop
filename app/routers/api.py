"""API routes for position management."""
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_active_user, get_client_ip, get_user_agent
from app.models.user import User, AuditLog

logger = logging.getLogger(__name__)
from app.core.security import (
    encrypt_api_key, decrypt_api_key,
    generate_data_key, unwrap_data_key, encrypt_with_data_key, decrypt_with_data_key
)
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


# ============ Helper Functions ============

async def log_credential_audit(
    db: AsyncSession,
    action: str,
    user: User,
    credential_id: int,
    request: Request,
    success: bool = True,
    error_message: str = None
):
    """Log credential-related audit events."""
    audit = AuditLog(
        user_id=user.id,
        action=action,
        resource_type="api_credential",
        resource_id=credential_id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        success=success,
        error_message=error_message
    )
    db.add(audit)
    await db.commit()


# ============ API Credentials ============

@router.post("/credentials", response_model=APICredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: APICredentialCreate,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new API credential with envelope encryption."""
    # Generate data key for this credential
    raw_data_key, wrapped_data_key = generate_data_key()
    
    # Encrypt API key and secret with data key
    api_key_encrypted = encrypt_with_data_key(data.api_key, raw_data_key)
    api_secret_encrypted = encrypt_with_data_key(data.api_secret, raw_data_key)
    
    credential = APICredential(
        user_id=user.id,
        name=data.name,
        exchange=data.exchange,
        wrapped_data_key=wrapped_data_key,
        api_key_encrypted=api_key_encrypted,
        api_secret_encrypted=api_secret_encrypted,
        is_testnet=data.is_testnet
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    
    # Log audit
    await log_credential_audit(db, "bind_api_key", user, credential.id, request)
    
    logger.info(f"User {user.id} created API credential {credential.id} for {credential.exchange}")
    return credential


@router.get("/credentials", response_model=List[APICredentialResponse])
async def list_credentials(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's API credentials."""
    result = await db.execute(
        select(APICredential)
        .where(APICredential.user_id == user.id)
        .order_by(desc(APICredential.created_at))
    )
    return result.scalars().all()


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete API credential (unbind)."""
    result = await db.execute(
        select(APICredential)
        .where(APICredential.id == credential_id)
        .where(APICredential.user_id == user.id)
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    # Log audit before deletion
    await log_credential_audit(db, "unbind_api_key", user, credential_id, request)
    
    await db.delete(credential)
    await db.commit()
    
    logger.info(f"User {user.id} deleted API credential {credential_id}")
    return {"message": "Credential deleted"}


def decrypt_credential(credential: APICredential) -> tuple:
    """Decrypt API key and secret from a credential using envelope encryption."""
    # Check if using envelope encryption (has wrapped_data_key) or legacy
    if credential.wrapped_data_key:
        # Envelope encryption
        data_key = unwrap_data_key(credential.wrapped_data_key)
        api_key = decrypt_with_data_key(credential.api_key_encrypted, data_key)
        api_secret = decrypt_with_data_key(credential.api_secret_encrypted, data_key)
    else:
        # Legacy encryption
        api_key = decrypt_api_key(credential.api_key_encrypted)
        api_secret = decrypt_api_key(credential.api_secret_encrypted)
    
    return api_key, api_secret


@router.get("/credentials/{credential_id}/unmanaged-positions")
async def get_unmanaged_positions(
    credential_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get positions that are not yet managed by any config."""
    # Get credential (only user's own)
    result = await db.execute(
        select(APICredential)
        .where(APICredential.id == credential_id)
        .where(APICredential.user_id == user.id)
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    # Get all configs for this credential
    configs_result = await db.execute(
        select(PositionConfig).where(PositionConfig.credential_id == credential_id)
    )
    configs = configs_result.scalars().all()
    
    # Build set of managed position keys (symbol + side)
    managed_keys = {(c.symbol, c.side) for c in configs}
    
    exchange = None
    try:
        logger.info(f"Connecting to {credential.exchange} (testnet={credential.is_testnet})")
        
        # Decrypt credentials
        api_key, api_secret = decrypt_credential(credential)
        
        # Create exchange service
        exchange = ExchangeService(
            exchange_id=credential.exchange,
            api_key=api_key,
            api_secret=api_secret,
            sandbox=credential.is_testnet
        )
        
        # Get all positions from exchange
        logger.info("Fetching positions from exchange...")
        all_positions = await exchange.get_positions()
        logger.info(f"Found {len(all_positions)} positions")
        
        # Filter out managed positions
        unmanaged = [
            {
                "symbol": p.symbol,
                "side": p.side,
                "size": p.size,
                "entry_price": p.entry_price,
                "unrealized_pnl": p.unrealized_pnl,
                "leverage": p.leverage,
                "current_price": p.current_price,
                "liquidation_price": p.liquidation_price
            }
            for p in all_positions
            if (p.symbol, p.side) not in managed_keys
        ]
        
        logger.info(f"Returning {len(unmanaged)} unmanaged positions")
        return unmanaged
        
    except Exception as e:
        logger.exception(f"Failed to fetch positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch positions: {str(e)}")
    finally:
        if exchange:
            await exchange.close()


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
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually adjust stop loss price."""
    result = await db.execute(select(PositionConfig).where(PositionConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Get credential (verify ownership)
    cred_result = await db.execute(
        select(APICredential)
        .where(APICredential.id == config.credential_id)
        .where(APICredential.user_id == user.id)
    )
    credential = cred_result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    old_stop = config.current_stop_price
    
    try:
        # Decrypt credentials
        api_key, api_secret = decrypt_credential(credential)
        
        # Create exchange service and update stop
        exchange = ExchangeService(
            exchange_id=credential.exchange,
            api_key=api_key,
            api_secret=api_secret,
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

