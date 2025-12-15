"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class APICredentialCreate(BaseModel):
    """Schema for creating API credentials."""
    name: str = Field(..., min_length=1, max_length=100)
    exchange: str = Field(default="binance")
    api_key: str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)
    is_testnet: bool = False


class APICredentialResponse(BaseModel):
    """Schema for API credential response (without secrets)."""
    id: int
    name: str
    exchange: str
    is_testnet: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PositionConfigCreate(BaseModel):
    """Schema for creating a new position config."""
    symbol: str = Field(..., description="Trading pair, e.g., BTC/USDT:USDT")
    side: str = Field(..., pattern="^(long|short)$")
    credential_id: int
    
    # User adjustable parameters
    timeframe: str = Field(default="15min", pattern="^(10min|15min|30min|1h|4h)$")
    sl_offset: float = Field(default=0.0, ge=0.0, description="额外的价格止损offset")
    delay_bars: int = Field(default=0, ge=0, description="开仓前n根K线不调整止损线")
    
    # Optional SuperTrend parameters (use defaults if not provided)
    ema_len: int = Field(default=8, ge=2)
    atr_len: int = Field(default=14, ge=1)
    base_mult: float = Field(default=2.0, ge=0.1)
    vol_lookback: int = Field(default=20, ge=2)
    vol_power: float = Field(default=1.0, ge=0.1)
    trend_lookback: int = Field(default=25, ge=2)
    trend_impact: float = Field(default=0.4, ge=0.0, le=1.0)
    mult_min: float = Field(default=1.0, ge=0.1)
    mult_max: float = Field(default=4.0, ge=0.5)
    confirm_bars: int = Field(default=1, ge=1)


class PositionConfigUpdate(BaseModel):
    """Schema for updating position config."""
    timeframe: Optional[str] = Field(None, pattern="^(10min|15min|30min|1h|4h)$")
    sl_offset: Optional[float] = Field(None, ge=0.0)
    delay_bars: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(active|paused|stopped)$")
    
    # Optional SuperTrend parameters
    ema_len: Optional[int] = Field(None, ge=2)
    atr_len: Optional[int] = Field(None, ge=1)
    base_mult: Optional[float] = Field(None, ge=0.1)
    vol_lookback: Optional[int] = Field(None, ge=2)
    vol_power: Optional[float] = Field(None, ge=0.1)
    trend_lookback: Optional[int] = Field(None, ge=2)
    trend_impact: Optional[float] = Field(None, ge=0.0, le=1.0)
    mult_min: Optional[float] = Field(None, ge=0.1)
    mult_max: Optional[float] = Field(None, ge=0.5)
    confirm_bars: Optional[int] = Field(None, ge=1)


class PositionConfigResponse(BaseModel):
    """Schema for position config response."""
    id: int
    symbol: str
    side: str
    credential_id: int
    
    timeframe: str
    sl_offset: float
    delay_bars: int
    
    ema_len: int
    atr_len: int
    base_mult: float
    vol_lookback: int
    vol_power: float
    trend_lookback: int
    trend_impact: float
    mult_min: float
    mult_max: float
    confirm_bars: int
    
    status: str
    current_stop_price: Optional[float]
    bars_since_open: int
    last_regime: int
    
    created_at: datetime
    updated_at: datetime
    last_checked_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PositionResponse(BaseModel):
    """Schema for position snapshot response."""
    id: int
    config_id: int
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: Optional[float]
    unrealized_pnl: float
    leverage: int
    liquidation_price: Optional[float]
    current_stop_price: Optional[float]
    calculated_stop_price: Optional[float]
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OperationLogResponse(BaseModel):
    """Schema for operation log response."""
    id: int
    config_id: Optional[int]
    symbol: Optional[str]
    action: str
    message: str
    old_value: Optional[float]
    new_value: Optional[float]
    success: bool
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    total_positions: int
    active_tasks: int
    paused_tasks: int
    total_unrealized_pnl: float
    last_update: Optional[datetime]


class StopLossAdjustment(BaseModel):
    """Manual stop loss adjustment request."""
    new_stop_price: float = Field(..., gt=0)

