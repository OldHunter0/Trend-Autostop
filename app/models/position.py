"""Database models for positions and configurations."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class PositionSide(str, enum.Enum):
    """Position side enum."""
    LONG = "long"
    SHORT = "short"


class TaskStatus(str, enum.Enum):
    """Task status enum."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class APICredential(Base):
    """Encrypted API credentials storage."""
    __tablename__ = "api_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    exchange = Column(String(50), nullable=False, default="binance")
    api_key_encrypted = Column(Text, nullable=False)
    api_secret_encrypted = Column(Text, nullable=False)
    is_testnet = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PositionConfig(Base):
    """Configuration for a managed position/task."""
    __tablename__ = "position_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Position identification
    symbol = Column(String(50), nullable=False)  # e.g., 'BTC/USDT:USDT'
    side = Column(String(10), nullable=False)  # 'long' or 'short'
    
    # API credential reference
    credential_id = Column(Integer, nullable=False)
    
    # Strategy parameters
    timeframe = Column(String(20), nullable=False, default="15min")
    sl_offset = Column(Float, nullable=False, default=0.0)
    delay_bars = Column(Integer, nullable=False, default=0)  # 生效delay: 开仓前n根K线不调整
    
    # SuperTrend parameters
    ema_len = Column(Integer, default=8)
    atr_len = Column(Integer, default=14)
    base_mult = Column(Float, default=2.0)
    vol_lookback = Column(Integer, default=20)
    vol_power = Column(Float, default=1.0)
    trend_lookback = Column(Integer, default=25)
    trend_impact = Column(Float, default=0.4)
    mult_min = Column(Float, default=1.0)
    mult_max = Column(Float, default=4.0)
    confirm_bars = Column(Integer, default=1)
    
    # State tracking
    status = Column(String(20), default=TaskStatus.ACTIVE.value)
    current_stop_price = Column(Float, nullable=True)
    bars_since_open = Column(Integer, default=0)  # 用于tracking delay
    last_regime = Column(Integer, default=0)  # 1=bull, -1=bear, 0=neutral
    
    # Entry info (for tracking delay)
    entry_bar_time = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)


class Position(Base):
    """Real-time position snapshot from exchange."""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, nullable=False)
    
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)
    size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    leverage = Column(Integer, default=1)
    liquidation_price = Column(Float, nullable=True)
    
    # Stop loss tracking
    current_stop_price = Column(Float, nullable=True)
    calculated_stop_price = Column(Float, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OperationLog(Base):
    """Log of all operations performed."""
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, nullable=True)
    symbol = Column(String(50), nullable=True)
    
    action = Column(String(50), nullable=False)  # 'update_stop', 'cancel_order', 'create_order', 'error', 'info'
    message = Column(Text, nullable=False)
    
    old_value = Column(Float, nullable=True)
    new_value = Column(Float, nullable=True)
    
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

