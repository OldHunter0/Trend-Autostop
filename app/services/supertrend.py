"""
SuperTrend Strategy Implementation.
Replicates the HD Volatility Trail indicator logic from Pine Script.
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class SuperTrendResult:
    """Result of SuperTrend calculation."""
    regime: int  # 1 = bullish, -1 = bearish, 0 = neutral
    trail_long: float  # Stop loss level for long position
    trail_short: float  # Stop loss level for short position
    current_stop: float  # Current effective stop loss based on regime
    is_flip: bool  # Whether a regime flip occurred
    flip_direction: Optional[str]  # 'bull' or 'bear' if flipped


class SuperTrendCalculator:
    """
    Calculates SuperTrend trailing stop levels.
    
    Based on Pine Script: HD Volatility Trail [Stats+OffsetSim]
    """
    
    def __init__(
        self,
        ema_len: int = 8,
        atr_len: int = 14,
        base_mult: float = 2.0,
        vol_lookback: int = 20,
        vol_power: float = 1.0,
        trend_lookback: int = 25,
        trend_impact: float = 0.4,
        mult_min: float = 1.0,
        mult_max: float = 4.0,
        confirm_bars: int = 1
    ):
        """
        Initialize SuperTrend calculator with strategy parameters.
        
        Args:
            ema_len: EMA length for basis calculation
            atr_len: ATR length
            base_mult: Base ATR multiplier
            vol_lookback: Volatility lookback period
            vol_power: Volatility stretch sensitivity
            trend_lookback: Trend memory length
            trend_impact: Trend impact factor (0-1)
            mult_min: Minimum effective multiplier
            mult_max: Maximum effective multiplier
            confirm_bars: Bars needed to confirm flip
        """
        self.ema_len = ema_len
        self.atr_len = atr_len
        self.base_mult = base_mult
        self.vol_lookback = vol_lookback
        self.vol_power = vol_power
        self.trend_lookback = trend_lookback
        self.trend_impact = trend_impact
        self.mult_min = mult_min
        self.mult_max = mult_max
        self.confirm_bars = confirm_bars
    
    def _calculate_ema(self, data: pd.Series, length: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return data.ewm(span=length, adjust=False).mean()
    
    def _calculate_atr(self, df: pd.DataFrame, length: int) -> pd.Series:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=length).mean()
        return atr
    
    def calculate(self, df: pd.DataFrame) -> SuperTrendResult:
        """
        Calculate SuperTrend levels for the given OHLCV data.
        
        Args:
            df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
                Should contain enough historical data for calculations.
        
        Returns:
            SuperTrendResult with current regime and stop levels
        """
        if len(df) < max(self.ema_len, self.atr_len, self.vol_lookback, self.trend_lookback) + 10:
            raise ValueError("Insufficient data for SuperTrend calculation")
        
        # Make a copy to avoid modifying original
        df = df.copy()
        
        # Core calculations
        basis = self._calculate_ema(df['close'], self.ema_len)
        atr = self._calculate_atr(df, self.atr_len)
        atr_avg = atr.rolling(window=self.vol_lookback).mean()
        
        # Volatility stretch
        vol_stretch_raw = np.where(atr_avg == 0, 1.0, atr / atr_avg)
        vol_stretch = np.power(vol_stretch_raw, self.vol_power)
        
        # Trend calculation
        slope = basis - basis.shift(1)
        dir_step = np.where(slope >= 0, 1.0, -1.0)
        dir_step_series = pd.Series(dir_step, index=df.index)
        trend_memory = self._calculate_ema(dir_step_series, self.trend_lookback)
        trend_boost = 1.0 + self.trend_impact * np.abs(trend_memory)
        
        # Final multiplier
        mult_raw = self.base_mult * vol_stretch * trend_boost
        mult_upper = np.minimum(mult_raw, self.mult_max)
        mult_final = np.maximum(mult_upper, self.mult_min)
        
        # Bands
        band_top = basis + mult_final * atr
        band_bot = basis - mult_final * atr
        
        # Trailing logic with state
        n = len(df)
        trail_long = np.full(n, np.nan)
        trail_short = np.full(n, np.nan)
        regime = np.zeros(n, dtype=int)
        bull_count = np.zeros(n, dtype=int)
        bear_count = np.zeros(n, dtype=int)
        
        # Initialize
        trail_long[0] = band_bot.iloc[0]
        trail_short[0] = band_top.iloc[0]
        
        close = df['close'].values
        
        for i in range(1, n):
            # Count consecutive bars above/below trails
            if close[i] > trail_short[i-1]:
                bull_count[i] = bull_count[i-1] + 1
            else:
                bull_count[i] = 0
                
            if close[i] < trail_long[i-1]:
                bear_count[i] = bear_count[i-1] + 1
            else:
                bear_count[i] = 0
            
            # Update trails based on current regime
            if regime[i-1] == 1:  # Bullish
                trail_long[i] = max(band_bot.iloc[i], trail_long[i-1])
                trail_short[i] = band_top.iloc[i]
            elif regime[i-1] == -1:  # Bearish
                trail_short[i] = min(band_top.iloc[i], trail_short[i-1])
                trail_long[i] = band_bot.iloc[i]
            else:  # Neutral
                trail_long[i] = band_bot.iloc[i]
                trail_short[i] = band_top.iloc[i]
            
            # Determine regime
            regime[i] = regime[i-1]
            
            if regime[i-1] == 0:
                if bull_count[i] >= self.confirm_bars:
                    regime[i] = 1
                elif bear_count[i] >= self.confirm_bars:
                    regime[i] = -1
            elif regime[i-1] == 1 and bear_count[i] >= self.confirm_bars:
                regime[i] = -1
            elif regime[i-1] == -1 and bull_count[i] >= self.confirm_bars:
                regime[i] = 1
        
        # Get latest values
        current_regime = int(regime[-1])
        current_trail_long = float(trail_long[-1])
        current_trail_short = float(trail_short[-1])
        prev_regime = int(regime[-2]) if n > 1 else 0
        
        # Determine current stop based on regime
        if current_regime == 1:
            current_stop = current_trail_long
        elif current_regime == -1:
            current_stop = current_trail_short
        else:
            current_stop = current_trail_long  # Default to long trail
        
        # Check for flip
        is_flip = current_regime != prev_regime and current_regime != 0
        flip_direction = None
        if is_flip:
            flip_direction = 'bull' if current_regime == 1 else 'bear'
        
        return SuperTrendResult(
            regime=current_regime,
            trail_long=current_trail_long,
            trail_short=current_trail_short,
            current_stop=current_stop,
            is_flip=is_flip,
            flip_direction=flip_direction
        )
    
    def calculate_with_offset(
        self, 
        df: pd.DataFrame, 
        sl_offset: float = 0.0
    ) -> Tuple[SuperTrendResult, float]:
        """
        Calculate SuperTrend with additional stop loss offset.
        
        Args:
            df: OHLCV DataFrame
            sl_offset: Additional price offset for stop loss
        
        Returns:
            Tuple of (SuperTrendResult, adjusted_stop_level)
        """
        result = self.calculate(df)
        
        # Apply offset based on regime
        if result.regime == 1:  # Long position - move stop down
            adjusted_stop = result.current_stop - sl_offset
        elif result.regime == -1:  # Short position - move stop up
            adjusted_stop = result.current_stop + sl_offset
        else:
            adjusted_stop = result.current_stop
        
        return result, adjusted_stop


def get_supertrend_calculator(**kwargs) -> SuperTrendCalculator:
    """Factory function to create SuperTrend calculator."""
    return SuperTrendCalculator(**kwargs)

