"""
EdgeX交易类型定义 v3.5

定义了策略中使用的各种数据类型和枚举
@version 3.5
@date 2025-10-08
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List
from decimal import Decimal


class TradeDirection(str, Enum):
    """交易方向"""
    LONG = "LONG"      # 做多
    SHORT = "SHORT"    # 做空
    HOLD = "HOLD"      # 持有/观望


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"           # 待成交
    FILLED = "FILLED"             # 已成交
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 部分成交
    CANCELLED = "CANCELLED"       # 已取消
    REJECTED = "REJECTED"         # 已拒绝


@dataclass
class PriceData:
    """价格数据（K线数据）"""
    timestamp: int      # 时间戳（毫秒）
    open: float         # 开盘价
    high: float         # 最高价
    low: float          # 最低价
    close: float        # 收盘价
    volume: float       # 成交量


@dataclass
class TradeSignal:
    """交易信号"""
    symbol: str                     # 交易对
    direction: TradeDirection       # 交易方向
    confidence: float               # 信号置信度（0-1）
    price: float                    # 建议价格
    stop_loss: float               # 止损价格
    take_profit: float             # 止盈价格
    reason: str = ""               # 信号原因


@dataclass
class Position:
    """持仓信息"""
    symbol: str                     # 交易对
    contract_id: str               # 合约ID
    direction: TradeDirection      # 持仓方向
    size: float                    # 持仓数量
    entry_price: float             # 开仓价格
    current_price: float = 0.0     # 当前价格
    unrealized_pnl: float = 0.0    # 未实现盈亏
    leverage: int = 1              # 杠杆倍数
    stop_loss: float = 0.0         # 止损价
    take_profit: float = 0.0       # 止盈价
    opening_time: int = 0          # 开仓时间戳
    margin: float = 0.0            # 保证金
    

@dataclass
class Order:
    """订单信息"""
    symbol: str                    # 交易对
    side: str                      # 订单方向（BUY/SELL）
    order_type: str                # 订单类型（LIMIT/MARKET）
    quantity: float                # 数量
    price: float = 0.0             # 价格（限价单使用）
    leverage: int = 1              # 杠杆
    client_order_id: str = ""      # 客户端订单ID
    order_id: str = ""             # 交易所订单ID
    status: OrderStatus = OrderStatus.PENDING  # 订单状态
    filled_quantity: float = 0.0   # 已成交数量
    average_price: float = 0.0     # 平均成交价
    created_time: int = 0          # 创建时间
    updated_time: int = 0          # 更新时间


# 为了兼容性，导出OrderSide和OrderType
class OrderSide(str, Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """订单类型"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    POST_ONLY = "POST_ONLY"


@dataclass
class AccountInfo:
    """账户信息"""
    balance: float                      # 账户余额
    available_balance: float            # 可用余额
    margin_used: float = 0.0            # 已用保证金
    unrealized_pnl: float = 0.0         # 未实现盈亏
    positions: Dict[str, Position] = None  # 持仓字典
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = {}


@dataclass
class TradeRecord:
    """交易记录"""
    symbol: str                    # 交易对
    direction: TradeDirection      # 交易方向
    size: float                    # 交易数量
    entry_price: float             # 开仓价
    exit_price: float              # 平仓价
    pnl: float                     # 盈亏
    timestamp: int                 # 时间戳
    duration: int                  # 持仓时长（秒）
    commission: float = 0.0        # 手续费
    slippage: float = 0.0          # 滑点


@dataclass
class OrderBookLevel:
    """订单簿级别"""
    price: float       # 价格
    quantity: float    # 数量
    

@dataclass
class OrderBook:
    """订单簿"""
    symbol: str                      # 交易对
    bids: List[OrderBookLevel]       # 买单
    asks: List[OrderBookLevel]       # 卖单
    timestamp: int                   # 时间戳
    
    def get_best_bid(self) -> Optional[OrderBookLevel]:
        """获取最佳买价"""
        return self.bids[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[OrderBookLevel]:
        """获取最佳卖价"""
        return self.asks[0] if self.asks else None
    
    def get_mid_price(self) -> float:
        """获取中间价"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / 2.0
        return 0.0
    
    def get_spread(self) -> float:
        """获取买卖价差"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return 0.0
    
    def get_spread_pct(self) -> float:
        """获取价差百分比"""
        mid_price = self.get_mid_price()
        if mid_price > 0:
            return self.get_spread() / mid_price
        return 0.0

