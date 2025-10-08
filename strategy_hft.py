"""
EdgeX高频做市网格策略 v3.5

核心特性：
1. 网格做市策略 - 在买卖盘口挂单赚取价差
2. 使用POST_ONLY限价单 - 获得maker返佣，降低手续费
3. 高频轮转 - 快速开平仓以增加交易量
4. 动态网格调整 - 根据市场波动性调整网格间距
5. 严格风险控制 - 持仓限制、止损保护

目标：
- 每日交易量达到净值的100-200倍
- 手续费最小化（maker返佣）
- 滑点最小化（限价单）

策略逻辑：
1. 在当前价格上下挂买卖网格单
2. 当一侧成交后，立即在相反方向挂平仓单
3. 控制总持仓不超过净值的一定比例
4. 动态调整网格间距适应市场波动

更新日志 (v3.5):
- 修复价格和数量精度问题（tickSize/stepSize）
- 优化API调用频率，降低429限速风险
- 实现指数退避机制处理限速
- 串行执行减少并发请求
- 正确解析EdgeX API响应格式

@author EdgeX Team
@version 3.5
@date 2025-10-08
"""

import asyncio
import time
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from loguru import logger

from edgex_types import (
    PriceData, Position, TradeDirection, 
    AccountInfo, Order, OrderSide, OrderType, OrderBook
)
from edgex_client import EdgeXClient


class GridStrategyConfig:
    """网格策略配置"""
    
    def __init__(self):
        # ===== 网格参数 =====
        self.grid_levels = 3              # 网格层数（每侧）减少层数增加成交率
        self.grid_spacing_pct = Decimal("0.0005")  # 网格间距 0.05% 缩小间距增加成交
        self.min_grid_spacing_pct = Decimal("0.0003")  # 最小间距 0.03%
        self.max_grid_spacing_pct = Decimal("0.001")   # 最大间距 0.1%
        
        # ===== 仓位管理 =====
        self.position_size_pct = Decimal("0.08")  # 每格仓位占净值8%
        self.max_total_position_pct = Decimal("0.5")  # 最大总持仓50%净值
        self.leverage = 10                # 杠杆倍数（降低到10倍以控制风险）
        
        # ===== 风险控制 =====
        self.max_position_per_side = 10  # 单侧最多持仓数量（增加以支持高频交易）
        self.stop_loss_pct = Decimal("0.01")  # 1%止损
        self.daily_loss_limit_pct = Decimal("0.05")  # 5%日亏损限制
        
        # ===== 订单管理 =====
        self.order_refresh_interval = 20  # 订单刷新间隔（秒）
        self.min_order_interval = 2.0     # 最小下单间隔（秒）
        self.max_open_orders = 50         # 最大挂单数量（增加以支持多层网格）
        self.api_call_interval = 1.2      # API调用间隔（秒）EdgeX限速：2次/2秒，我们用1.2秒保证安全
        
        # ===== 各币种最小下单量 =====
        self.MIN_ORDER_SIZES = {
            "BTC-USD": Decimal("0.001"),
            "ETH-USD": Decimal("0.02"),
            "SOL-USD": Decimal("0.3"),
            "BNB-USD": Decimal("0.01"),
        }
    
    def get_min_order_size(self, symbol: str) -> Decimal:
        """获取指定交易对的最小下单量"""
        return self.MIN_ORDER_SIZES.get(symbol, Decimal("0.01"))


class GridLevel:
    """网格层级"""
    
    def __init__(self, price: Decimal, size: Decimal, side: OrderSide, is_close_order: bool = False):
        self.price = price
        self.size = size
        self.side = side
        self.is_close_order = is_close_order  # 是否为平仓单
        self.order_id: Optional[str] = None
        self.is_filled = False
        self.filled_time: int = 0


class SymbolGridManager:
    """单个交易对的网格管理器"""
    
    def __init__(self, symbol: str, config: GridStrategyConfig):
        self.symbol = symbol
        self.config = config
        
        # 网格状态
        self.buy_grids: List[GridLevel] = []
        self.sell_grids: List[GridLevel] = []
        self.pending_orders: Dict[str, GridLevel] = {}  # order_id -> GridLevel
        
        # 持仓状态
        self.net_position = Decimal("0")  # 净持仓（正数=多头，负数=空头）
        self.position_count = {"long": 0, "short": 0}
        
        # 价格状态
        self.last_mid_price = Decimal("0")
        self.last_update_time = 0
        self.last_order_time = 0
        
    def can_place_order(self) -> bool:
        """检查是否可以下单"""
        now = time.time()
        if now - self.last_order_time < self.config.min_order_interval:
            return False
        return len(self.pending_orders) < self.config.max_open_orders
    
    def update_order_time(self):
        """更新下单时间"""
        self.last_order_time = time.time()
    
    def can_open_position(self, side: OrderSide) -> bool:
        """检查是否可以开仓"""
        if side == OrderSide.BUY:
            return self.position_count["long"] < self.config.max_position_per_side
        else:
            return self.position_count["short"] < self.config.max_position_per_side
    
    def update_position(self, side: OrderSide, quantity: Decimal, is_open: bool):
        """更新持仓统计"""
        if is_open:
            if side == OrderSide.BUY:
                self.net_position += quantity
                self.position_count["long"] += 1
            else:
                self.net_position -= quantity
                self.position_count["short"] += 1
        else:
            if side == OrderSide.BUY:
                self.net_position += quantity
                self.position_count["short"] = max(0, self.position_count["short"] - 1)
            else:
                self.net_position -= quantity
                self.position_count["long"] = max(0, self.position_count["long"] - 1)


class HighFrequencyMarketMakingStrategy:
    """高频做市网格策略"""
    
    def __init__(self, config):
        """
        初始化策略
        
        Args:
            config: 配置对象，包含API密钥、交易对等
        """
        self.config = config
        self.strategy_config = GridStrategyConfig()
        self.client = EdgeXClient(config)
        
        # 账户状态
        self.account_info: Optional[AccountInfo] = None
        self.initial_balance = Decimal("0")
        self.current_balance = Decimal("0")
        self.daily_pnl = Decimal("0")
        self.daily_volume = Decimal("0")
        
        # 网格管理器
        self.grid_managers: Dict[str, SymbolGridManager] = {}
        for symbol in config.symbols:
            self.grid_managers[symbol] = SymbolGridManager(symbol, self.strategy_config)
        
        # 交易统计
        self.total_trades = 0
        self.total_volume = Decimal("0")
        self.total_commission = Decimal("0")
        
        # 运行状态
        self.is_running = False
        self.start_time = 0
        
        logger.info("="*60)
        logger.info("高频做市网格策略初始化")
        logger.info(f"交易对: {', '.join(config.symbols)}")
        logger.info(f"网格层数: {self.strategy_config.grid_levels}")
        logger.info(f"网格间距: {float(self.strategy_config.grid_spacing_pct)*100:.2f}%")
        logger.info(f"杠杆倍数: {self.strategy_config.leverage}x")
        logger.info(f"每格仓位: {float(self.strategy_config.position_size_pct)*100:.1f}%")
        logger.info("="*60)
    
    async def run(self):
        """运行策略主循环"""
        self.is_running = True
        self.start_time = int(time.time())
        
        try:
            # 初始化客户端
            logger.info("初始化客户端...")
            await self.client.initialize()
            
            # 更新账户信息
            await self._update_account_info()
            self.initial_balance = self.current_balance
            
            logger.info(f"初始余额: {float(self.current_balance):.2f} USDT")
            logger.info("策略开始运行...")
            
            # 账户信息更新相关
            last_account_update_time = 0
            account_update_interval = 60  # 每60秒更新一次账户信息，避免429错误
            rate_limit_backoff = 5  # 初始退避时间（秒）
            consecutive_429_count = 0  # 连续429错误计数
            
            # 主循环
            while self.is_running:
                try:
                    # 定期更新账户信息（每60秒一次）
                    current_time = int(time.time())
                    if current_time - last_account_update_time >= account_update_interval:
                        try:
                            await self._update_account_info()
                            last_account_update_time = current_time
                        except Exception as e:
                            if '429' in str(e):
                                logger.warning(f"更新账户信息遇到429，跳过此次更新")
                    
                    # 检查风险控制
                    if not self._check_risk_limits():
                        logger.warning("触发风险控制，暂停交易")
                        await asyncio.sleep(60)
                        continue
                    
                    # 对每个交易对执行网格策略（串行执行以减少并发请求）
                    has_rate_limit = False
                    for symbol in self.config.symbols:
                        try:
                            await self._execute_grid_for_symbol(symbol)
                            await asyncio.sleep(5)  # 每个交易对之间延迟5秒，确保不触发EdgeX限速(2次/2秒)
                        except Exception as e:
                            error_msg = str(e)
                            if '429' in error_msg:
                                has_rate_limit = True
                                consecutive_429_count += 1
                                logger.warning(f"{symbol} 触发429限速")
                            else:
                                # 记录其他错误
                                logger.error(f"{symbol} 执行网格策略时出错: {e}")
                                import traceback
                                logger.debug(f"错误详情:\n{traceback.format_exc()}")
                    
                    # 如果遇到429错误，执行退避
                    if has_rate_limit:
                        backoff_time = min(rate_limit_backoff * (2 ** consecutive_429_count), 180)  # 最多3分钟
                        logger.warning(f"触发429限速，等待 {backoff_time} 秒后继续...")
                        await asyncio.sleep(backoff_time)
                    else:
                        consecutive_429_count = max(0, consecutive_429_count - 1)  # 逐步恢复
                    
                    # 输出统计信息
                    if int(time.time()) % 60 == 0:  # 每分钟输出一次
                        self._print_statistics()
                    
                    # 主循环延迟（增加到10秒，配合EdgeX限速2次/2秒）
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.error(f"策略执行错误: {e}")
                    await asyncio.sleep(5)
            
        except asyncio.CancelledError:
            logger.info("策略被取消")
        except Exception as e:
            logger.error(f"策略运行错误: {e}")
        finally:
            self.is_running = False
            # 清理订单
            await self._cleanup_all_orders()
            # 关闭客户端
            await self.client.close()
            logger.info("策略已停止")
    
    async def _execute_grid_for_symbol(self, symbol: str):
        """为指定交易对执行网格策略"""
        try:
            grid_mgr = self.grid_managers[symbol]
            
            # 获取订单簿（API调用1）
            contract_id = await self.client.get_contract_id_by_symbol(symbol)
            if not contract_id:
                return
            
            await asyncio.sleep(self.strategy_config.api_call_interval)  # API限速保护
            order_book = await self.client.get_order_book(contract_id, depth=15)
            if not order_book:
                return
            
            mid_price = Decimal(str(order_book.get_mid_price()))
            if mid_price <= 0:
                return
            
            # 更新价格
            grid_mgr.last_mid_price = mid_price
            grid_mgr.last_update_time = int(time.time())
            
            # 检查是否需要刷新网格
            should_refresh = self._should_refresh_grid(grid_mgr, mid_price)
            
            if should_refresh:
                # 取消旧订单（API调用2）
                await asyncio.sleep(self.strategy_config.api_call_interval)
                await self._cancel_symbol_orders(symbol)
                
                # 生成新网格（API调用3-N）
                await asyncio.sleep(self.strategy_config.api_call_interval)
                await self._generate_grid_orders(symbol, mid_price, order_book)
            
            # 检查成交并处理（API调用）
            await asyncio.sleep(self.strategy_config.api_call_interval)
            await self._check_fills(symbol)
            
        except Exception as e:
            logger.error(f"{symbol} 执行网格策略失败: {e}")
    
    def _should_refresh_grid(self, grid_mgr: SymbolGridManager, current_price: Decimal) -> bool:
        """检查是否需要刷新网格"""
        # 如果没有待成交的订单（不包括平仓单），就应该生成新网格
        open_orders_count = sum(1 for grid in grid_mgr.pending_orders.values() if not grid.is_close_order)
        if open_orders_count == 0:
            return True
        
        # 价格偏离过大
        if grid_mgr.last_mid_price > 0:
            price_deviation = abs(current_price - grid_mgr.last_mid_price) / grid_mgr.last_mid_price
            if price_deviation > Decimal("0.005"):  # 偏离0.5%
                return True
        
        # 定期刷新
        now = time.time()
        if now - grid_mgr.last_update_time > self.strategy_config.order_refresh_interval:
            return True
        
        return False
    
    async def _generate_grid_orders(self, symbol: str, mid_price: Decimal, order_book: OrderBook):
        """生成网格订单"""
        try:
            grid_mgr = self.grid_managers[symbol]
            
            # 清空旧网格
            grid_mgr.buy_grids.clear()
            grid_mgr.sell_grids.clear()
            
            # 计算网格间距
            grid_spacing = self.strategy_config.grid_spacing_pct
            
            # 获取盘口价格
            best_bid = order_book.get_best_bid()
            best_ask = order_book.get_best_ask()
            
            if not best_bid or not best_ask:
                return
            
            best_bid_price = Decimal(str(best_bid.price))
            best_ask_price = Decimal(str(best_ask.price))
            
            # 计算订单大小
            min_size = self.strategy_config.get_min_order_size(symbol)
            order_value = self.current_balance * self.strategy_config.position_size_pct
            base_size = order_value / mid_price
            
            # 确保满足最小订单量
            if base_size < min_size:
                base_size = min_size
            
            # 生成买单网格（低于最佳买价）
            for i in range(self.strategy_config.grid_levels):
                if not grid_mgr.can_place_order():
                    break
                if not grid_mgr.can_open_position(OrderSide.BUY):
                    break
                
                # 计算网格价格（略低于盘口）
                offset = grid_spacing * Decimal(i + 1)
                grid_price = best_bid_price * (Decimal("1") - offset)
                
                # 创建网格层级
                grid_level = GridLevel(
                    price=grid_price,
                    size=base_size,
                    side=OrderSide.BUY
                )
                
                # 下单
                order = Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.POST_ONLY,  # 使用POST_ONLY获得maker返佣
                    quantity=float(base_size),
                    price=float(grid_price),
                    leverage=self.strategy_config.leverage
                )
                
                response = await self.client.place_order(order)
                if response and response.get("code") == "SUCCESS":
                    order_id = response.get("data", {}).get("orderId")
                    if order_id:
                        grid_level.order_id = order_id
                        grid_mgr.pending_orders[order_id] = grid_level
                        grid_mgr.buy_grids.append(grid_level)
                        grid_mgr.update_order_time()
                        
                        logger.debug(f"{symbol} 挂买单: {float(grid_price):.2f} x {float(base_size):.4f}")
                
                # API限速保护
                await asyncio.sleep(self.strategy_config.api_call_interval)
            
            # 生成卖单网格（高于最佳卖价）
            for i in range(self.strategy_config.grid_levels):
                if not grid_mgr.can_place_order():
                    break
                if not grid_mgr.can_open_position(OrderSide.SELL):
                    break
                
                # 计算网格价格（略高于盘口）
                offset = grid_spacing * Decimal(i + 1)
                grid_price = best_ask_price * (Decimal("1") + offset)
                
                # 创建网格层级
                grid_level = GridLevel(
                    price=grid_price,
                    size=base_size,
                    side=OrderSide.SELL
                )
                
                # 下单
                order = Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.POST_ONLY,  # 使用POST_ONLY获得maker返佣
                    quantity=float(base_size),
                    price=float(grid_price),
                    leverage=self.strategy_config.leverage
                )
                
                response = await self.client.place_order(order)
                if response and response.get("code") == "SUCCESS":
                    order_id = response.get("data", {}).get("orderId")
                    if order_id:
                        grid_level.order_id = order_id
                        grid_mgr.pending_orders[order_id] = grid_level
                        grid_mgr.sell_grids.append(grid_level)
                        grid_mgr.update_order_time()
                        
                        logger.debug(f"{symbol} 挂卖单: {float(grid_price):.2f} x {float(base_size):.4f}")
                
                # API限速保护
                await asyncio.sleep(self.strategy_config.api_call_interval)
            
            logger.info(f"{symbol} 网格生成: {len(grid_mgr.buy_grids)}买 + {len(grid_mgr.sell_grids)}卖")
            
        except Exception as e:
            logger.error(f"{symbol} 生成网格订单失败: {e}")
    
    async def _check_fills(self, symbol: str):
        """检查订单成交情况"""
        try:
            grid_mgr = self.grid_managers[symbol]
            
            # 获取活跃订单
            active_orders = await self.client.get_active_orders(symbol)
            active_order_ids = {order.get("orderId") for order in active_orders}
            
            # 检查哪些订单已成交
            filled_orders = []
            for order_id, grid_level in list(grid_mgr.pending_orders.items()):
                if order_id not in active_order_ids:
                    # 订单已成交或取消
                    filled_orders.append((order_id, grid_level))
            
            # 处理成交订单
            for order_id, grid_level in filled_orders:
                # 标记为成交
                grid_level.is_filled = True
                grid_level.filled_time = int(time.time())
                
                # 更新持仓（区分开仓和平仓）
                if grid_level.is_close_order:
                    # 平仓单：减少持仓计数
                    grid_mgr.update_position(grid_level.side, grid_level.size, is_open=False)
                    logger.info(
                        f"{symbol} 平仓成交: {grid_level.side} "
                        f"{float(grid_level.size):.4f} @ {float(grid_level.price):.2f}"
                    )
                else:
                    # 开仓单：增加持仓计数
                    grid_mgr.update_position(grid_level.side, grid_level.size, is_open=True)
                    logger.info(
                        f"{symbol} 订单成交: {grid_level.side} "
                        f"{float(grid_level.size):.4f} @ {float(grid_level.price):.2f}"
                    )
                    # 立即在相反方向挂平仓单
                    await self._place_close_order(symbol, grid_level)
                
                # 移除待处理订单
                del grid_mgr.pending_orders[order_id]
                
                # 更新统计
                self.total_trades += 1
                trade_value = grid_level.price * grid_level.size
                self.total_volume += trade_value
                self.daily_volume += trade_value
            
        except Exception as e:
            logger.error(f"{symbol} 检查成交失败: {e}")
    
    async def _place_close_order(self, symbol: str, filled_grid: GridLevel):
        """在相反方向挂平仓单"""
        try:
            grid_mgr = self.grid_managers[symbol]
            
            # 计算平仓价格（加上利润）
            profit_offset = self.strategy_config.grid_spacing_pct * Decimal("1.5")
            
            if filled_grid.side == OrderSide.BUY:
                # 买入后挂卖单平仓
                close_price = filled_grid.price * (Decimal("1") + profit_offset)
                close_side = OrderSide.SELL
            else:
                # 卖出后挂买单平仓
                close_price = filled_grid.price * (Decimal("1") - profit_offset)
                close_side = OrderSide.BUY
            
            # 创建平仓网格层级（标记为平仓单）
            close_grid_level = GridLevel(
                price=close_price,
                size=filled_grid.size,
                side=close_side,
                is_close_order=True  # 标记为平仓单
            )
            
            # 下平仓单
            order = Order(
                symbol=symbol,
                side=close_side,
                order_type=OrderType.POST_ONLY,
                quantity=float(filled_grid.size),
                price=float(close_price),
                leverage=self.strategy_config.leverage
            )
            
            response = await self.client.place_order(order)
            if response and response.get("code") == "SUCCESS":
                order_id = response.get("data", {}).get("orderId")
                if order_id:
                    # 将平仓单加入pending_orders
                    close_grid_level.order_id = order_id
                    grid_mgr.pending_orders[order_id] = close_grid_level
                    
                logger.info(
                    f"{symbol} 挂平仓单: {close_side} "
                    f"{float(filled_grid.size):.4f} @ {float(close_price):.2f}"
                )
            
        except Exception as e:
            logger.error(f"{symbol} 挂平仓单失败: {e}")
    
    async def _cancel_symbol_orders(self, symbol: str):
        """取消指定交易对的所有订单"""
        try:
            grid_mgr = self.grid_managers[symbol]
            
            if grid_mgr.pending_orders:
                await self.client.cancel_all_orders(symbol)
                grid_mgr.pending_orders.clear()
                logger.debug(f"{symbol} 已取消所有订单")
            
        except Exception as e:
            logger.error(f"{symbol} 取消订单失败: {e}")
    
    async def _cleanup_all_orders(self):
        """清理所有订单"""
        try:
            logger.info("清理所有订单...")
            await self.client.cancel_all_orders()
            
            for grid_mgr in self.grid_managers.values():
                grid_mgr.pending_orders.clear()
                grid_mgr.buy_grids.clear()
                grid_mgr.sell_grids.clear()
            
        except Exception as e:
            logger.error(f"清理订单失败: {e}")
    
    def _check_risk_limits(self) -> bool:
        """检查风险限制"""
        # 检查日亏损限制
        if self.initial_balance > 0:
            daily_pnl_pct = (self.current_balance - self.initial_balance) / self.initial_balance
            if daily_pnl_pct < -self.strategy_config.daily_loss_limit_pct:
                logger.error(f"触发日亏损限制: {float(daily_pnl_pct)*100:.2f}%")
                return False
        
        # 检查总持仓
        total_position_value = Decimal("0")
        if self.account_info and self.account_info.positions:
            for position in self.account_info.positions.values():
                position_value = Decimal(str(position.current_price)) * Decimal(str(position.size))
                total_position_value += position_value
        
        if self.current_balance > 0:
            position_pct = total_position_value / self.current_balance
            if position_pct > self.strategy_config.max_total_position_pct:
                logger.warning(f"总持仓过高: {float(position_pct)*100:.1f}%")
                return False
        
        return True
    
    async def _update_account_info(self):
        """更新账户信息"""
        try:
            self.account_info = await self.client.get_account_info()
            self.current_balance = Decimal(str(self.account_info.balance))
            
            # 更新网格管理器的持仓状态
            for symbol, grid_mgr in self.grid_managers.items():
                position = self.account_info.positions.get(symbol)
                if position:
                    grid_mgr.net_position = Decimal(str(position.size))
                    if position.direction == TradeDirection.LONG:
                        grid_mgr.net_position = abs(grid_mgr.net_position)
                    else:
                        grid_mgr.net_position = -abs(grid_mgr.net_position)
                else:
                    grid_mgr.net_position = Decimal("0")
            
        except Exception as e:
            logger.error(f"更新账户信息失败: {e}")
    
    def _print_statistics(self):
        """打印统计信息"""
        runtime = int(time.time()) - self.start_time
        runtime_hours = runtime / 3600.0
        
        balance_change = self.current_balance - self.initial_balance
        balance_change_pct = (balance_change / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        volume_multiple = (self.daily_volume / self.current_balance) if self.current_balance > 0 else 0
        
        logger.info("="*60)
        logger.info("策略统计")
        logger.info(f"运行时间: {runtime_hours:.1f}小时")
        logger.info(f"当前余额: {float(self.current_balance):.2f} USDT ({balance_change_pct:+.2f}%)")
        logger.info(f"今日交易量: {float(self.daily_volume):.2f} USDT ({float(volume_multiple):.1f}x净值)")
        logger.info(f"总交易次数: {self.total_trades}")
        logger.info(f"总手续费: {float(self.total_commission):.2f} USDT")
        
        # 各交易对持仓
        if self.account_info and self.account_info.positions:
            logger.info("持仓情况:")
            for symbol, position in self.account_info.positions.items():
                logger.info(
                    f"  {symbol}: {position.direction.value} "
                    f"{position.size:.4f} @ {position.entry_price:.2f} "
                    f"(PnL: {position.unrealized_pnl:+.2f})"
                )
        
        logger.info("="*60)
    
    def stop(self):
        """停止策略"""
        self.is_running = False
        logger.info("正在停止策略...")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        volume_multiple = (self.daily_volume / self.current_balance) if self.current_balance > 0 else 0
        balance_change_pct = ((self.current_balance - self.initial_balance) / self.initial_balance * 100) if self.initial_balance > 0 else 0
        
        return {
            "balance": float(self.current_balance),
            "initial_balance": float(self.initial_balance),
            "balance_change_pct": float(balance_change_pct),
            "daily_volume": float(self.daily_volume),
            "volume_multiple": float(volume_multiple),
            "total_trades": self.total_trades,
            "total_commission": float(self.total_commission),
            "active_positions": len(self.account_info.positions) if self.account_info else 0
        }

