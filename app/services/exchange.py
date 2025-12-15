"""
Exchange service for interacting with crypto exchanges via CCXT.
"""
import ccxt.async_support as ccxt
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass


@dataclass
class Position:
    """Trading position data."""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    unrealized_pnl: float
    leverage: int
    margin_type: str
    current_price: float
    liquidation_price: Optional[float] = None


@dataclass
class StopOrder:
    """Stop loss order data."""
    order_id: str
    symbol: str
    side: str
    stop_price: float
    size: float
    status: str


class ExchangeService:
    """Service for exchange operations."""
    
    TIMEFRAME_MAP = {
        "10min": "10m",
        "15min": "15m",
        "30min": "30m",
        "1h": "1h",
        "4h": "4h"
    }
    
    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: str = "",
        api_secret: str = "",
        sandbox: bool = False
    ):
        """
        Initialize exchange service.
        
        Args:
            exchange_id: Exchange identifier (binance, okx, bybit)
            api_key: API key
            api_secret: API secret
            sandbox: Use testnet if available
        """
        self.exchange_id = exchange_id.lower()
        self._exchange: Optional[ccxt.Exchange] = None
        self._api_key = api_key
        self._api_secret = api_secret
        self._sandbox = sandbox
    
    async def _get_exchange(self) -> ccxt.Exchange:
        """Get or create exchange instance."""
        if self._exchange is None:
            exchange_class = getattr(ccxt, self.exchange_id)
            
            # Base config
            config = {
                'apiKey': self._api_key,
                'secret': self._api_secret,
                'enableRateLimit': True,
                'timeout': 30000,  # 30 seconds timeout
                'options': {
                    'adjustForTimeDifference': True,
                }
            }
            
            # Exchange-specific options
            if self.exchange_id == 'bybit':
                # Bybit V5 API uses 'linear' for USDT perpetual contracts
                config['options']['defaultType'] = 'linear'
                # Skip fetching currencies to speed up initialization
                config['options']['fetchCurrencies'] = False
            elif self.exchange_id == 'okx':
                config['options']['defaultType'] = 'swap'
            else:
                # Binance and others
                config['options']['defaultType'] = 'future'
            
            self._exchange = exchange_class(config)
            
            if self._sandbox:
                self._exchange.set_sandbox_mode(True)
            
            await self._exchange.load_markets()
        
        return self._exchange
    
    async def close(self):
        """Close exchange connection."""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "15min",
        limit: int = 200
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candlestick data.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT:USDT')
            timeframe: Candle timeframe
            limit: Number of candles to fetch
        
        Returns:
            DataFrame with OHLCV data
        """
        exchange = await self._get_exchange()
        tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        
        ohlcv = await exchange.fetch_ohlcv(symbol, tf, limit=limit)
        
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get open positions.
        
        Args:
            symbol: Optional symbol filter
        
        Returns:
            List of Position objects
        """
        exchange = await self._get_exchange()
        
        if symbol:
            positions = await exchange.fetch_positions([symbol])
        else:
            positions = await exchange.fetch_positions()
        
        result = []
        for pos in positions:
            # Only include positions with actual size
            size = float(pos.get('contracts', 0) or pos.get('contractSize', 0))
            if size == 0:
                continue
            
            result.append(Position(
                symbol=pos['symbol'],
                side='long' if pos['side'] == 'long' else 'short',
                size=size,
                entry_price=float(pos.get('entryPrice', 0)),
                unrealized_pnl=float(pos.get('unrealizedPnl', 0)),
                leverage=int(pos.get('leverage', 1)),
                margin_type=pos.get('marginType', 'cross'),
                current_price=float(pos.get('markPrice', 0)),
                liquidation_price=float(pos['liquidationPrice']) if pos.get('liquidationPrice') else None
            ))
        
        return result
    
    async def get_stop_orders(self, symbol: str) -> List[StopOrder]:
        """
        Get stop loss orders for a symbol.
        
        Args:
            symbol: Trading pair
        
        Returns:
            List of StopOrder objects
        """
        exchange = await self._get_exchange()
        
        try:
            orders = await exchange.fetch_open_orders(symbol)
            
            stop_orders = []
            for order in orders:
                if order.get('stopPrice'):
                    stop_orders.append(StopOrder(
                        order_id=order['id'],
                        symbol=order['symbol'],
                        side=order['side'],
                        stop_price=float(order['stopPrice']),
                        size=float(order['amount']),
                        status=order['status']
                    ))
            
            return stop_orders
        except Exception:
            return []
    
    async def create_stop_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        stop_price: float,
        reduce_only: bool = True
    ) -> Dict[str, Any]:
        """
        Create a stop loss order.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Order size
            stop_price: Stop trigger price
            reduce_only: Whether order should only reduce position
        
        Returns:
            Order result
        """
        exchange = await self._get_exchange()
        
        params = {
            'stopPrice': stop_price,
            'reduceOnly': reduce_only,
        }
        
        # Exchange specific params
        if self.exchange_id == 'binance':
            params['type'] = 'STOP_MARKET'
        elif self.exchange_id == 'bybit':
            params['triggerPrice'] = stop_price
        
        order = await exchange.create_order(
            symbol=symbol,
            type='stop',
            side=side,
            amount=amount,
            price=None,
            params=params
        )
        
        return order
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
        
        Returns:
            True if successful
        """
        exchange = await self._get_exchange()
        
        try:
            await exchange.cancel_order(order_id, symbol)
            return True
        except Exception:
            return False
    
    async def update_stop_loss(
        self,
        symbol: str,
        position_side: str,
        new_stop_price: float,
        amount: float
    ) -> Dict[str, Any]:
        """
        Update stop loss by canceling old and creating new order.
        
        Args:
            symbol: Trading pair
            position_side: 'long' or 'short'
            new_stop_price: New stop price
            amount: Position size
        
        Returns:
            New order result
        """
        # Cancel existing stop orders
        existing_stops = await self.get_stop_orders(symbol)
        for stop in existing_stops:
            await self.cancel_order(symbol, stop.order_id)
        
        # Create new stop order
        # For long position, sell to close; for short, buy to close
        order_side = 'sell' if position_side == 'long' else 'buy'
        
        return await self.create_stop_order(
            symbol=symbol,
            side=order_side,
            amount=amount,
            stop_price=new_stop_price
        )
    
    async def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get current ticker for symbol."""
        exchange = await self._get_exchange()
        ticker = await exchange.fetch_ticker(symbol)
        return {
            'last': float(ticker['last']),
            'bid': float(ticker['bid']),
            'ask': float(ticker['ask']),
            'high': float(ticker['high']),
            'low': float(ticker['low'])
        }


async def create_exchange_service(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    sandbox: bool = False
) -> ExchangeService:
    """Factory function to create exchange service."""
    return ExchangeService(
        exchange_id=exchange_id,
        api_key=api_key,
        api_secret=api_secret,
        sandbox=sandbox
    )

