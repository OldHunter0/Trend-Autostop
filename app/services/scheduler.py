"""
Scheduler service for automated stop loss management.
Runs on each timeframe candle close to calculate and update stop losses.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.security import decrypt_api_key
from app.models.position import PositionConfig, Position, OperationLog, APICredential
from app.services.supertrend import SuperTrendCalculator
from app.services.exchange import ExchangeService

logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = AsyncIOScheduler()

# Timeframe to cron mapping
TIMEFRAME_CRON: Dict[str, dict] = {
    "10min": {"minute": "*/10"},
    "15min": {"minute": "*/15"},
    "30min": {"minute": "*/30"},
    "1h": {"minute": "0"},
    "4h": {"minute": "0", "hour": "*/4"}
}

# Timeframe to minutes
TIMEFRAME_MINUTES = {
    "10min": 10,
    "15min": 15,
    "30min": 30,
    "1h": 60,
    "4h": 240
}


async def log_operation(
    db: AsyncSession,
    config_id: int,
    symbol: str,
    action: str,
    message: str,
    old_value: float = None,
    new_value: float = None,
    success: bool = True,
    error_message: str = None
):
    """Helper to create operation log."""
    log = OperationLog(
        config_id=config_id,
        symbol=symbol,
        action=action,
        message=message,
        old_value=old_value,
        new_value=new_value,
        success=success,
        error_message=error_message
    )
    db.add(log)
    await db.commit()


async def process_config(config: PositionConfig, db: AsyncSession):
    """
    Process a single position config:
    1. Fetch latest OHLCV data
    2. Calculate SuperTrend
    3. Check delay_bars condition
    4. Update stop loss if needed
    """
    logger.info(f"Processing config {config.id}: {config.symbol} ({config.side})")
    
    try:
        # Get API credential
        cred_result = await db.execute(
            select(APICredential).where(APICredential.id == config.credential_id)
        )
        credential = cred_result.scalar_one_or_none()
        if not credential:
            await log_operation(
                db, config.id, config.symbol, "error",
                "Credential not found", success=False
            )
            return
        
        # Create exchange service
        exchange = ExchangeService(
            exchange_id=credential.exchange,
            api_key=decrypt_api_key(credential.api_key_encrypted),
            api_secret=decrypt_api_key(credential.api_secret_encrypted),
            sandbox=credential.is_testnet
        )
        
        try:
            # Check if position still exists
            positions = await exchange.get_positions(config.symbol)
            position = next((p for p in positions if p.side == config.side), None)
            
            if not position:
                logger.info(f"No position found for {config.symbol} ({config.side})")
                # Update or create position record as closed
                pos_result = await db.execute(
                    select(Position).where(Position.config_id == config.id)
                )
                pos_record = pos_result.scalar_one_or_none()
                if pos_record:
                    await db.delete(pos_record)
                
                config.status = "stopped"
                await log_operation(
                    db, config.id, config.symbol, "info",
                    "Position closed, config stopped"
                )
                await db.commit()
                return
            
            # Update position record
            pos_result = await db.execute(
                select(Position).where(Position.config_id == config.id)
            )
            pos_record = pos_result.scalar_one_or_none()
            
            if not pos_record:
                pos_record = Position(config_id=config.id)
                db.add(pos_record)
            
            pos_record.symbol = position.symbol
            pos_record.side = position.side
            pos_record.size = position.size
            pos_record.entry_price = position.entry_price
            pos_record.current_price = position.current_price
            pos_record.unrealized_pnl = position.unrealized_pnl
            pos_record.leverage = position.leverage
            pos_record.liquidation_price = position.liquidation_price
            
            # Fetch OHLCV data
            df = await exchange.fetch_ohlcv(
                config.symbol,
                timeframe=config.timeframe,
                limit=200
            )
            
            # Create SuperTrend calculator with config params
            calculator = SuperTrendCalculator(
                ema_len=config.ema_len,
                atr_len=config.atr_len,
                base_mult=config.base_mult,
                vol_lookback=config.vol_lookback,
                vol_power=config.vol_power,
                trend_lookback=config.trend_lookback,
                trend_impact=config.trend_impact,
                mult_min=config.mult_min,
                mult_max=config.mult_max,
                confirm_bars=config.confirm_bars
            )
            
            # Calculate SuperTrend
            result, adjusted_stop = calculator.calculate_with_offset(df, config.sl_offset)
            
            # Update config state
            config.last_regime = result.regime
            config.last_checked_at = datetime.utcnow()
            
            # Increment bars since open
            config.bars_since_open += 1
            
            # Check delay condition
            if config.bars_since_open <= config.delay_bars:
                logger.info(
                    f"Delay active: {config.bars_since_open}/{config.delay_bars} bars. "
                    f"Skip stop adjustment for {config.symbol}"
                )
                await log_operation(
                    db, config.id, config.symbol, "info",
                    f"Delay active ({config.bars_since_open}/{config.delay_bars}), skip adjustment"
                )
                pos_record.calculated_stop_price = adjusted_stop
                await db.commit()
                return
            
            # Check if stop needs updating
            old_stop = config.current_stop_price
            
            # Determine if we should update
            should_update = False
            if old_stop is None:
                should_update = True
            elif config.side == "long":
                # For long: only move stop UP (trail up)
                should_update = adjusted_stop > old_stop
            else:
                # For short: only move stop DOWN (trail down)
                should_update = adjusted_stop < old_stop
            
            if should_update:
                logger.info(
                    f"Updating stop for {config.symbol}: {old_stop} -> {adjusted_stop}"
                )
                
                # Update stop on exchange
                await exchange.update_stop_loss(
                    symbol=config.symbol,
                    position_side=config.side,
                    new_stop_price=adjusted_stop,
                    amount=position.size
                )
                
                config.current_stop_price = adjusted_stop
                pos_record.current_stop_price = adjusted_stop
                pos_record.calculated_stop_price = adjusted_stop
                
                await log_operation(
                    db, config.id, config.symbol, "update_stop",
                    f"Stop updated: {old_stop:.4f} -> {adjusted_stop:.4f}",
                    old_value=old_stop,
                    new_value=adjusted_stop
                )
            else:
                logger.info(
                    f"No stop update needed for {config.symbol}. "
                    f"Current: {old_stop}, Calculated: {adjusted_stop}"
                )
                pos_record.calculated_stop_price = adjusted_stop
            
            await db.commit()
            
        finally:
            await exchange.close()
            
    except Exception as e:
        logger.error(f"Error processing config {config.id}: {e}")
        await log_operation(
            db, config.id, config.symbol, "error",
            f"Processing error: {str(e)[:200]}",
            success=False,
            error_message=str(e)
        )


async def run_scheduled_job(timeframe: str):
    """
    Run the scheduled job for a specific timeframe.
    Processes all active configs with matching timeframe.
    """
    logger.info(f"Running scheduled job for timeframe: {timeframe}")
    
    async with async_session_maker() as db:
        try:
            # Get all active configs for this timeframe
            result = await db.execute(
                select(PositionConfig).where(
                    PositionConfig.status == "active",
                    PositionConfig.timeframe == timeframe
                )
            )
            configs = result.scalars().all()
            
            logger.info(f"Found {len(configs)} active configs for {timeframe}")
            
            # Process each config
            for config in configs:
                try:
                    await process_config(config, db)
                except Exception as e:
                    logger.error(f"Failed to process config {config.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Scheduler job error: {e}")


def setup_scheduler():
    """Setup scheduler jobs for all timeframes."""
    for timeframe, cron_params in TIMEFRAME_CRON.items():
        # Add a small delay (10 seconds) after candle close to ensure data is available
        trigger = CronTrigger(**cron_params)
        
        scheduler.add_job(
            run_scheduled_job,
            trigger=trigger,
            args=[timeframe],
            id=f"supertrend_{timeframe}",
            replace_existing=True,
            misfire_grace_time=60
        )
        logger.info(f"Scheduled job for {timeframe}: {cron_params}")


def start_scheduler():
    """Start the scheduler."""
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def run_manual_check(config_id: int) -> dict:
    """
    Manually trigger a check for a specific config.
    Useful for testing or forcing an immediate update.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(PositionConfig).where(PositionConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        
        if not config:
            return {"error": "Config not found"}
        
        await process_config(config, db)
        return {"message": f"Manual check completed for config {config_id}"}

