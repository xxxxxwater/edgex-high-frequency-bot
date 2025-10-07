"""
多币种加密货币高频交易策略（超快速启动版本 v3.4）

支持交易对：
- BTC-USDT (比特币)
- ETH-USDT (以太坊)
- SOL-USDT (Solana)
- BNB-USDT (BNB)

核心特性：
- 基于1分钟K线的均线偏离策略（5周期MA + 1周期MA）
- 24小时不间断交易
- 固定仓位管理（每币种5%）
- 严格风险控制（±0.4%止盈止损）
- ✅ 多交易对并发交易
- ✅ 各币种独立最小下单量检查
- ✅ 超快启动（仅需5分钟K线数据）

主要优化：
1. ✅ 快速启动：从20分钟优化到5分钟
2. ✅ 仓位计算：固定5%仓位，无波动率调整
3. ✅ 实时信号：1周期MA接近实时价格
4. ✅ 最小下单量：各币种独立配置和检查
5. ✅ 多交易对支持：同时监控和交易多个币种

@author EdgeX Team
@version 3.4 - 超快速启动
"""

import asyncio
import math
import time
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from websocket_client import RealTimePriceStream

from edgex_types import (
    PriceData, TradeSignal, Position, TradeDirection, 
    AccountInfo, Order, OrderSide, OrderType, TradeRecord
)
from edgex_client import EdgeXClient


class StrategyConfig:
    """策略配置"""
    
    # 各币种最小下单量配置
    MIN_ORDER_SIZES = {
        "BTC-USDT": Decimal("0.001"),   # BTC最小0.001
        "ETH-USDT": Decimal("0.02"),    # ETH最小0.02
        "SOL-USDT": Decimal("0.3"),     # SOL最小0.3
        "BNB-USDT": Decimal("0.01"),    # BNB最小0.01
        # 合约ID映射
        "10000001": Decimal("0.001"),   # BTC
        "10000002": Decimal("0.02"),    # ETH
        "10000003": Decimal("0.3"),     # SOL
        "10000004": Decimal("0.01"),    # BNB
    }
    
    def __init__(self):
        # 仓位配置
        self.base_position_size = Decimal("0.05")  # 5%仓位（每个币种）
        self.leverage = 50  # 杠杆倍数
        
        # 止盈止损
        self.take_profit_pct = Decimal("0.004")  # 0.4%止盈
        self.stop_loss_pct = Decimal("0.004")    # 0.4%止损
        
        # 均线参数（优化：减少等待时间）
        self.short_ma_period = 1
        self.medium_ma_period = 5
        self.deviation_threshold = Decimal("0.002")  # 0.2%偏离阈值
        
        # 最小下单量乘数
        self.min_balance_multiplier = Decimal("2")
    
    def get_min_order_size(self, symbol: str) -> Decimal:
        """
        获取指定交易对的最小下单量
        
        Args:
            symbol: 交易对名称或合约ID
            
        Returns:
            Decimal: 最小下单量
        """
        return self.MIN_ORDER_SIZES.get(symbol, Decimal("0.05"))


class HighFrequencyStrategy:
    """多币种高频交易策略"""
    
    # 市场配置（加密货币专用）
    MINUTES_PER_HOUR = 60
    HOURS_PER_DAY = 24
    DAYS_PER_YEAR = 365
    TRADING_MINUTES_PER_DAY = MINUTES_PER_HOUR * HOURS_PER_DAY
    
    def __init__(self, config):
        """
        初始化策略
        
        Args:
            config: 配置对象，包含API密钥、交易对列表等信息
        """
        self.config = config
        self.strategy_config = StrategyConfig()
        self.client = EdgeXClient(config)
        
        # 账户状态
        self.balance = Decimal("0")
        self.available_balance = Decimal("0")
        self.positions: Dict[str, Position] = {}
        
        # 交易记录（按交易对分类）
        self.trade_records: List[TradeRecord] = []
        self.equity_history: List[Decimal] = []
        self.price_history: Dict[str, List[PriceData]] = {}  # 价格历史记录
        
        # 各交易对的最后交易时间
        self.last_trade_times: Dict[str, int] = {}
        
        # WebSocket价格流
        self.price_stream: Optional[RealTimePriceStream] = None
        self.contract_ids: Dict[str, str] = {}  # 交易对到合约ID的映射
        
        # 运行状态
        self.is_running = False
        self.min_trade_interval = 5000  # 最小交易间隔（毫秒）
        self.max_trade_interval = 60000  # 最大交易间隔（毫秒）
        
        logger.info("="*60)
        logger.info("多币种高频策略初始化（v3.4 - WebSocket版）")
        logger.info(f"数据源: WebSocket实时价格流")
        logger.info(f"市场类型: 加密货币（24小时交易）")
        logger.info(f"交易对数量: {len(self.config.symbols)}")
        logger.info(f"交易对列表: {', '.join(self.config.symbols)}")
        logger.info(f"杠杆倍数: {self.strategy_config.leverage}x")
        logger.info("✅ 各币种最小下单量:")
        for symbol in self.config.symbols:
            min_size = self.strategy_config.get_min_order_size(symbol)
            logger.info(f"   - {symbol}: {min_size}")
        logger.info("="*60)
    
    async def run(self):
        """运行策略主循环"""
        self.is_running = True
        logger.info("策略开始运行...")
        
        try:
            # 初始化WebSocket连接
            await self._initialize_websocket()
            
            # 更新账户信息
            await self._update_account_info()
            
            # 启动WebSocket价格流
            if self.price_stream:
                await self.price_stream.start()
            
            while self.is_running:
                try:
                    # 对每个交易对执行策略
                    for symbol in self.config.symbols:
                        await self._execute_strategy_for_symbol(symbol)
                    
                    # 等待下次交易
                    await asyncio.sleep(1)  # 1秒间隔，WebSocket提供实时数据
                    
                except Exception as e:
                    logger.error(f"策略执行错误: {e}")
                    await asyncio.sleep(5)  # 出错后等待5秒
                    
        except asyncio.CancelledError:
            logger.info("策略被取消")
        finally:
            self.is_running = False
            if self.price_stream:
                await self.price_stream.stop()
            logger.info("策略已停止")
    
    async def _initialize_websocket(self):
        """初始化WebSocket连接"""
        try:
            # 获取合约ID映射
            for symbol in self.config.symbols:
                contract_id = await self.client.get_contract_id_by_symbol(symbol)
                if contract_id:
                    self.contract_ids[symbol] = contract_id
                    logger.info(f"映射 {symbol} -> {contract_id}")
                else:
                    logger.error(f"无法获取 {symbol} 的合约ID")
            
            # 确定base_url (WebSocket使用wss://，SDK会自动添加/api/v1/public/ws路径)
            if self.config.testnet:
                base_url = "wss://testnet.edgex.exchange"
            else:
                base_url = "wss://pro.edgex.exchange"
            
            # 创建价格流
            self.price_stream = RealTimePriceStream(
                symbols=self.config.symbols,
                contract_ids=self.contract_ids,
                base_url=base_url,
                account_id=int(self.config.account_id) if self.config.account_id else 0,
                stark_private_key=self.config.stark_private_key or ""
            )
            
            # 添加价格回调
            self.price_stream.add_price_callback(self._on_price_update)
            
            logger.info("WebSocket价格流初始化完成")
            
        except Exception as e:
            logger.error(f"WebSocket初始化失败: {e}")
            raise
    
    def _on_price_update(self, symbol: str, price_data: PriceData):
        """价格更新回调函数"""
        try:
            # 更新价格历史
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            
            self.price_history[symbol].append(price_data)
            
            # 保持历史记录在合理范围内
            if len(self.price_history[symbol]) > 1000:
                self.price_history[symbol] = self.price_history[symbol][-1000:]
            
            logger.debug(f"{symbol}: 价格更新 {price_data.close}")
            
        except Exception as e:
            logger.error(f"处理价格更新失败: {e}")
    
    def stop(self):
        """停止策略"""
        self.is_running = False
        logger.info("正在停止策略...")
    
    async def _update_account_info(self):
        """更新账户信息"""
        try:
            account_info = await self.client.get_account_info()
            self.balance = Decimal(str(account_info.balance))
            self.available_balance = Decimal(str(account_info.available_balance))
            self.positions = account_info.positions
            
            # 记录权益历史
            self.equity_history.append(self.balance)
            
            # 限制历史长度
            if len(self.equity_history) > 1000:
                self.equity_history = self.equity_history[-1000:]
                
        except Exception as e:
            logger.error(f"更新账户信息失败: {e}")
            raise
    
    async def _execute_strategy_for_symbol(self, symbol: str):
        """为指定交易对执行策略"""
        try:
            # 从WebSocket获取价格历史数据
            klines = self.price_history.get(symbol, [])
            
            if len(klines) < self.strategy_config.medium_ma_period:
                logger.debug(f"{symbol}: 价格数据不足 (收到{len(klines)}/需要{self.strategy_config.medium_ma_period})")
                return
            
            # 获取最新价格
            latest_price = klines[-1].close
            logger.debug(f"{symbol}: 当前价格: {latest_price}")
            
            # 生成交易信号
            signal = self._generate_signal(symbol, klines)
            
            # 检查是否有现有持仓
            if symbol in self.positions:
                await self._manage_position(symbol, signal, klines)
            else:
                await self._open_position(symbol, signal, klines)
                
        except Exception as e:
            logger.error(f"{symbol}: 执行策略失败 - {e}")
    
    def _generate_signal(self, symbol: str, klines: List[PriceData]) -> TradeSignal:
        """
        生成交易信号
        
        Args:
            symbol: 交易对
            klines: K线数据列表
            
        Returns:
            TradeSignal: 交易信号
        """
        if len(klines) < self.strategy_config.medium_ma_period:
            logger.warning(f"[信号生成] K线数据不足{self.strategy_config.medium_ma_period}根")
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.HOLD,
                confidence=0.0,
                price=0.0,
                stop_loss=0.0,
                take_profit=0.0
            )
        
        # 计算均线
        medium_ma = self._calculate_moving_average(klines, self.strategy_config.medium_ma_period)
        current_price = self._get_current_price(klines)
        price_deviation = self._calculate_price_deviation(current_price, medium_ma)
        
        # 判断方向
        if price_deviation > self.strategy_config.deviation_threshold:
            # 价格高于均线，做空
            direction = TradeDirection.SHORT
            stop_loss = float(current_price * (Decimal("1") + self.strategy_config.stop_loss_pct))
            take_profit = float(current_price * (Decimal("1") - self.strategy_config.take_profit_pct))
            logger.info(f"[信号] {symbol} 做空 - 偏离: {float(price_deviation) * 100:.4f}%")
            
        elif price_deviation < -self.strategy_config.deviation_threshold:
            # 价格低于均线，做多
            direction = TradeDirection.LONG
            stop_loss = float(current_price * (Decimal("1") - self.strategy_config.stop_loss_pct))
            take_profit = float(current_price * (Decimal("1") + self.strategy_config.take_profit_pct))
            logger.info(f"[信号] {symbol} 做多 - 偏离: {float(price_deviation) * 100:.4f}%")
            
        else:
            # 持有
            logger.debug(f"[信号] {symbol} 持有 - 偏离: {float(price_deviation) * 100:.4f}%")
            return TradeSignal(
                symbol=symbol,
                direction=TradeDirection.HOLD,
                confidence=0.0,
                price=float(current_price),
                stop_loss=0.0,
                take_profit=0.0
            )
        
        confidence = float(abs(price_deviation))
        
        return TradeSignal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            price=float(current_price),
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    async def _open_position(self, symbol: str, signal: TradeSignal, klines: List[PriceData]):
        """开仓"""
        if signal.direction == TradeDirection.HOLD:
            return
        
        try:
            # 计算仓位大小
            current_price = Decimal(str(signal.price))
            
            # 获取该币种的最小下单量
            min_order_size = self.strategy_config.get_min_order_size(symbol)
            
            # 检查最小余额要求
            min_required_balance = (
                min_order_size * 
                current_price * 
                self.strategy_config.min_balance_multiplier
            )
            
            if self.available_balance < min_required_balance:
                logger.warning(
                    f"[开仓] {symbol} 账户余额不足，无法满足最小下单量要求 "
                    f"(当前: {float(self.available_balance):.2f} USDT, "
                    f"最小需求: {float(min_required_balance):.2f} USDT)"
                )
                return
            
            # 计算仓位大小
            position_size = self._calculate_position_size(
                self.available_balance,
                self.strategy_config.base_position_size,
                current_price,
                min_order_size
            )
            
            # 验证最小下单量
            if position_size < min_order_size:
                logger.error(
                    f"[开仓] {symbol} 计算仓位({float(position_size)}) "
                    f"小于最小下单量({float(min_order_size)})"
                )
                return
            
            # 计算杠杆仓位
            leverage_position = position_size * Decimal(str(self.strategy_config.leverage))
            
            logger.info(f"[开仓] {symbol} ====================================")
            logger.info(f"[开仓] 当前价格: {float(current_price):.2f} USDT")
            logger.info(f"[开仓] 基础仓位: {float(position_size):.6f}")
            logger.info(f"[开仓] 杠杆仓位: {float(leverage_position):.6f} ({self.strategy_config.leverage}x)")
            logger.info(f"[开仓] ✅ 仓位检查通过（>= {float(min_order_size)}）")
            logger.info(f"[开仓] ====================================")
            
            # 设置杠杆
            await self.client.set_leverage(symbol, self.strategy_config.leverage)
            
            # 创建订单
            order = Order(
                symbol=symbol,
                side=OrderSide.BUY if signal.direction == TradeDirection.LONG else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=float(leverage_position),
                leverage=self.strategy_config.leverage
            )
            
            # 下单
            result = await self.client.place_order(order)
            logger.info(f"[开仓] {symbol} 订单提交成功: {result}")
            
            # 记录交易时间
            self.last_trade_time = int(datetime.now().timestamp() * 1000)
            
        except Exception as e:
            logger.error(f"[开仓] {symbol} 失败: {e}")
    
    async def _manage_position(self, symbol: str, signal: TradeSignal, klines: List[PriceData]):
        """管理持仓（止盈止损）"""
        position = self.positions.get(symbol)
        if not position:
            return
        
        try:
            current_price = Decimal(str(self._get_current_price(klines)))
            entry_price = Decimal(str(position.entry_price))
            
            # 计算盈亏
            pnl = self._calculate_pnl(position, current_price)
            
            # 检查止盈
            if position.take_profit > 0:
                if position.direction == TradeDirection.LONG and current_price >= Decimal(str(position.take_profit)):
                    logger.info(f"[平仓] {symbol} 触发止盈 (价格: {float(current_price):.2f})")
                    await self._close_position(symbol, current_price, pnl)
                    return
                    
                elif position.direction == TradeDirection.SHORT and current_price <= Decimal(str(position.take_profit)):
                    logger.info(f"[平仓] {symbol} 触发止盈 (价格: {float(current_price):.2f})")
                    await self._close_position(symbol, current_price, pnl)
                    return
            
            # 检查止损
            if position.stop_loss > 0:
                if position.direction == TradeDirection.LONG and current_price <= Decimal(str(position.stop_loss)):
                    logger.info(f"[平仓] {symbol} 触发止损 (价格: {float(current_price):.2f})")
                    await self._close_position(symbol, current_price, pnl)
                    return
                    
                elif position.direction == TradeDirection.SHORT and current_price >= Decimal(str(position.stop_loss)):
                    logger.info(f"[平仓] {symbol} 触发止损 (价格: {float(current_price):.2f})")
                    await self._close_position(symbol, current_price, pnl)
                    return
            
            # 检查反向信号
            if signal.direction != TradeDirection.HOLD and signal.direction != position.direction:
                logger.info(f"[平仓] {symbol} 反向信号，平仓")
                await self._close_position(symbol, current_price, pnl)
                
        except Exception as e:
            logger.error(f"[管理持仓] {symbol} 失败: {e}")
    
    async def _close_position(self, symbol: str, exit_price: Decimal, pnl: Decimal):
        """平仓"""
        position = self.positions.get(symbol)
        if not position:
            return
        
        try:
            # 创建平仓订单（反向操作）
            order = Order(
                symbol=symbol,
                side=OrderSide.SELL if position.direction == TradeDirection.LONG else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=position.size,
                leverage=position.leverage
            )
            
            # 下单
            result = await self.client.place_order(order)
            logger.info(f"[平仓] {symbol} 订单提交成功: {result}")
            
            # 记录交易
            trade_record = TradeRecord(
                symbol=symbol,
                direction=position.direction,
                size=position.size,
                entry_price=position.entry_price,
                exit_price=float(exit_price),
                pnl=float(pnl),
                timestamp=int(datetime.now().timestamp()),
                duration=int(datetime.now().timestamp()) - position.opening_time
            )
            
            self.trade_records.append(trade_record)
            
            # 移除持仓
            del self.positions[symbol]
            
            logger.info(
                f"[平仓] {symbol} 完成 - "
                f"盈亏: {float(pnl):.4f} USDT, "
                f"收益率: {float(pnl / Decimal(str(position.entry_price)) / Decimal(str(position.size))) * 100:.2f}%"
            )
            
        except Exception as e:
            logger.error(f"[平仓] {symbol} 失败: {e}")
    
    def _calculate_position_size(
        self, 
        balance: Decimal, 
        base_position_pct: Decimal, 
        current_price: Decimal, 
        min_order_size: Decimal
    ) -> Decimal:
        """
        计算仓位大小（带最小下单量检查）
        
        Args:
            balance: 账户余额（USDT）
            base_position_pct: 基础仓位比例
            current_price: 当前价格
            min_order_size: 该币种的最小下单量
            
        Returns:
            Decimal: 仓位大小（币的数量）
        """
        if current_price <= 0:
            raise ValueError("当前价格必须大于零")
        if balance <= 0:
            raise ValueError("账户余额必须大于零")
        
        # 步骤1：计算基础投入金额
        base_amount = balance * base_position_pct
        
        # 步骤2：直接使用基础金额（不再调整波动率）
        adjusted_amount = base_amount
        
        # 步骤3：转换为币的数量
        calculated_size = adjusted_amount / current_price
        
        # 步骤5：最小下单量检查和调整
        final_size = calculated_size
        adjusted = False
        
        if calculated_size < min_order_size:
            logger.warning(
                f"[仓位计算] 计算仓位({float(calculated_size):.6f}) "
                f"小于最小值({float(min_order_size)})"
            )
            
            # 调整到最小值
            final_size = min_order_size
            adjusted = True
            
            # 检查调整后是否超过余额限制
            required_amount = final_size * current_price
            max_allowed_amount = balance * Decimal("0.5")  # 最多50%余额
            
            if required_amount > max_allowed_amount:
                raise ValueError(
                    f"最小仓位需要 {float(required_amount):.2f} USDT，"
                    f"超过余额50%限制 ({float(max_allowed_amount):.2f} USDT)"
                )
            
            logger.info(f"[仓位计算] ✅ 已调整到最小值 {float(min_order_size)}")
        
        # 详细日志
        logger.debug(f"[仓位计算] ====================================")
        logger.debug(f"[仓位计算] 账户余额: {float(balance):.2f} USDT")
        logger.debug(f"[仓位计算] 基础比例: {float(base_position_pct) * 100:.2f}%")
        logger.debug(f"[仓位计算] 基础金额: {float(base_amount):.2f} USDT")
        logger.debug(f"[仓位计算] 当前价格: {float(current_price):.2f} USDT")
        logger.debug(f"[仓位计算] 调整后金额: {float(adjusted_amount):.2f} USDT")
        logger.debug(f"[仓位计算] 计算仓位: {float(calculated_size):.4f} 币")
        
        if adjusted:
            logger.debug(f"[仓位计算] ⚠️ 已调整到最小值: {float(final_size):.4f} 币")
            logger.debug(f"[仓位计算] 实际需要: {float(final_size * current_price):.2f} USDT")
        else:
            logger.debug(f"[仓位计算] 最终仓位: {float(final_size):.4f} 币")
        
        logger.debug(f"[仓位计算] 实际占用: {float(final_size * current_price / balance) * 100:.2f}%")
        logger.debug(f"[仓位计算] 最小要求: {float(min_order_size)}")
        logger.debug(f"[仓位计算] ✅ 检查通过（仓位 >= 最小值）")
        logger.debug(f"[仓位计算] ====================================")
        
        return final_size.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    
    def _calculate_pnl(self, position: Position, current_price: Decimal) -> Decimal:
        """
        计算持仓盈亏
        
        Args:
            position: 持仓信息
            current_price: 当前价格
            
        Returns:
            Decimal: 盈亏金额
        """
        entry_price = Decimal(str(position.entry_price))
        size = Decimal(str(position.size))
        
        if position.direction == TradeDirection.LONG:
            return (current_price - entry_price) * size
        elif position.direction == TradeDirection.SHORT:
            return (entry_price - current_price) * size
        else:
            return Decimal("0")
    
    def _calculate_moving_average(self, klines: List[PriceData], period: int) -> Decimal:
        """
        计算移动平均线
        
        Args:
            klines: K线数据列表
            period: 周期
            
        Returns:
            Decimal: 移动平均值
        """
        if not klines or len(klines) < period:
            return Decimal("0")
        
        total_close = sum(Decimal(str(k.close)) for k in klines[-period:])
        return total_close / Decimal(str(period))
    
    def _get_current_price(self, klines: List[PriceData]) -> Decimal:
        """获取当前价格"""
        if not klines:
            return Decimal("0")
        return Decimal(str(klines[-1].close))
    
    def _calculate_price_deviation(self, current_price: Decimal, ma: Decimal) -> Decimal:
        """
        计算价格偏离度
        
        Args:
            current_price: 当前价格
            ma: 移动平均价格
            
        Returns:
            Decimal: 偏离度（百分比）
        """
        if ma == 0:
            return Decimal("0")
        deviation = current_price - ma
        return deviation / ma
    
    def _calculate_daily_volume(self) -> float:
        """计算每日交易量"""
        now = datetime.now()
        daily_volume = 0.0
        
        for record in self.trade_records:
            trade_time = datetime.fromtimestamp(record.timestamp)
            if (now - trade_time).total_seconds() < 86400:  # 24小时内
                daily_volume += record.size * record.entry_price
        
        return daily_volume
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        total_trades = len(self.trade_records)
        winning_trades = sum(1 for r in self.trade_records if r.pnl > 0)
        losing_trades = sum(1 for r in self.trade_records if r.pnl < 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        return {
            "balance": float(self.balance),
            "available_balance": float(self.available_balance),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "active_positions": len(self.positions),
            "trading_interval": self.min_trade_interval // 1000  # 转换为秒
        }

