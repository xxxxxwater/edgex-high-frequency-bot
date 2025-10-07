"""
数据类型定义
"""

from pydantic import BaseModel
from typing import Dict, List, Optional, Union
from datetime import datetime
from enum import Enum

class TradeDirection(str, Enum):
    """交易方向"""
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"

class OrderSide(str, Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    """订单类型"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class PriceData(BaseModel):
    """价格数据"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class TradeSignal(BaseModel):
    """交易信号"""
    symbol: str
    direction: TradeDirection
    confidence: float
    price: float
    stop_loss: float
    take_profit: float

class Position(BaseModel):
    """持仓信息"""
    symbol: str
    direction: TradeDirection
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    leverage: int
    opening_time: int

class AccountInfo(BaseModel):
    """账户信息"""
    balance: float
    available_balance: float
    positions: Dict[str, Position] = {}

class Order(BaseModel):
    """订单信息"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    leverage: int

class TradeRecord(BaseModel):
    """交易记录"""
    symbol: str
    direction: TradeDirection
    size: float
    entry_price: float
    exit_price: float
    pnl: float
    timestamp: int
    duration: int

class PerformanceReport(BaseModel):
    """性能报告"""
    timestamp: datetime
    portfolio_value: float
    current_volatility: float
    target_volatility: float
    volatility_ratio: float
    daily_volume: float
    volume_target: float
    volume_ratio: float
    today_trades: int
    today_pnl: float
    trading_interval: int

class WebSocketMessage(BaseModel):
    """WebSocket消息"""
    msg_type: str
    channel: Optional[str] = None
    time: Optional[str] = None
    content: Optional[Dict] = None

class MarketData(BaseModel):
    """市场数据"""
    symbol: str
    price: float
    volume: float
    timestamp: int
    bid: Optional[float] = None
    ask: Optional[float] = None

class OrderBook(BaseModel):
    """订单簿"""
    symbol: str
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]  # [[price, quantity], ...]
    timestamp: int

class KlineData(BaseModel):
    """K线数据"""
    symbol: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: str

class StrategyConfig(BaseModel):
    """策略配置"""
    base_position_size: float = 0.05  # 5%仓位
    leverage: int = 50  # 杠杆倍数
    take_profit_pct: float = 0.004  # 0.4%止盈
    stop_loss_pct: float = 0.004  # 0.4%止损
    short_ma_period: int = 5
    medium_ma_period: int = 20
    deviation_threshold: float = 0.002  # 0.2%偏离阈值
    target_volatility: float = 0.60  # 60%年化波动率
    min_order_size: float = 0.3  # 最小下单量（SOL）
    min_balance_multiplier: float = 1.2
