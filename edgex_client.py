"""
EdgeX客户端封装 v3.5

封装EdgeX SDK，提供更简洁的API接口
包含价格/数量精度处理和API响应解析

@version 3.5
@date 2025-10-08
"""

import asyncio
from typing import Dict, Any, Optional, List
from decimal import Decimal, ROUND_DOWN
from loguru import logger

from edgex_sdk import (
    Client,
    OrderSide as SDKOrderSide,
    OrderType as SDKOrderType,
    TimeInForce,
    CreateOrderParams,
    CancelOrderParams,
    GetActiveOrderParams,
    GetKLineParams,
    GetOrderBookDepthParams
)

from edgex_types import (
    AccountInfo, Position, Order, OrderBook, OrderBookLevel,
    TradeDirection, OrderSide, OrderType, OrderStatus, PriceData
)


class EdgeXClient:
    """EdgeX客户端封装类"""
    
    def __init__(self, config):
        """
        初始化客户端
        
        Args:
            config: 配置对象，包含API密钥、交易对等信息
        """
        self.config = config
        self.sdk_client = Client(
            base_url=config.base_url,
            account_id=config.account_id,
            stark_private_key=config.stark_private_key
        )
        
        # 缓存合约信息
        self.metadata = None
        self.contracts = {}
        self.symbol_to_contract_id = {}
        self.contract_tick_sizes = {}  # 价格精度（tickSize）
        self.contract_step_sizes = {}  # 数量精度（stepSize）
        
    async def initialize(self):
        """初始化客户端，获取元数据"""
        try:
            self.metadata = await self.sdk_client.get_metadata()
            contract_list = self.metadata.get("data", {}).get("contractList", [])
            
            for contract in contract_list:
                contract_id = contract.get("contractId")
                contract_name = contract.get("contractName", "")
                
                if contract_id:
                    self.contracts[contract_id] = contract
                    
                    # 缓存价格和数量精度
                    tick_size = contract.get("tickSize")
                    step_size = contract.get("stepSize")
                    if tick_size:
                        self.contract_tick_sizes[contract_id] = Decimal(tick_size)
                    if step_size:
                        self.contract_step_sizes[contract_id] = Decimal(step_size)
                    
                    # 存储原始合约名称映射
                    if contract_name:
                        self.symbol_to_contract_id[contract_name] = contract_id
                        
                        # 同时创建标准化格式的映射
                        # BTCUSD -> BTC-USD, BNB2USD -> BNB-USD
                        if contract_name.endswith("USD"):
                            # 移除USD后缀
                            base = contract_name[:-3]
                            # 处理包含"2"的情况 (BNB2USD -> BNB)
                            if "2" in base:
                                base = base.replace("2", "")
                            # 创建标准格式 BTC-USD
                            standard_symbol = f"{base}-USD"
                            self.symbol_to_contract_id[standard_symbol] = contract_id
            
            logger.info(f"已加载 {len(self.contracts)} 个合约")
            return True
            
        except Exception as e:
            logger.error(f"初始化客户端失败: {e}")
            return False
    
    async def get_contract_id_by_symbol(self, symbol: str) -> Optional[str]:
        """
        通过交易对名称获取合约ID
        
        Args:
            symbol: 交易对名称，如 BTC-USDT
            
        Returns:
            合约ID，如 10000001
        """
        return self.symbol_to_contract_id.get(symbol)
    
    def format_price(self, contract_id: str, price: float) -> str:
        """
        根据合约的tickSize格式化价格
        
        Args:
            contract_id: 合约ID
            price: 原始价格
            
        Returns:
            格式化后的价格字符串
        """
        tick_size = self.contract_tick_sizes.get(contract_id, Decimal("0.01"))
        price_decimal = Decimal(str(price))
        
        # 根据tickSize取整（向下取整）
        formatted_price = (price_decimal / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
        
        # 根据tick_size确定小数位数
        tick_str = str(tick_size)
        if '.' in tick_str:
            decimal_places = len(tick_str.split('.')[1].rstrip('0'))
        else:
            decimal_places = 0
        
        # 使用quantize确保正确的小数位数
        if decimal_places > 0:
            quantizer = Decimal('0.1') ** decimal_places
            formatted_price = formatted_price.quantize(quantizer)
        else:
            formatted_price = formatted_price.quantize(Decimal('1'))
        
        # 转换为字符串
        return str(formatted_price)
    
    def format_quantity(self, contract_id: str, quantity: float) -> str:
        """
        根据合约的stepSize格式化数量
        
        Args:
            contract_id: 合约ID
            quantity: 原始数量
            
        Returns:
            格式化后的数量字符串
        """
        step_size = self.contract_step_sizes.get(contract_id, Decimal("0.001"))
        quantity_decimal = Decimal(str(quantity))
        
        # 根据stepSize取整（向下取整）
        formatted_quantity = (quantity_decimal / step_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_size
        
        # 根据step_size确定小数位数
        step_str = str(step_size)
        if '.' in step_str:
            decimal_places = len(step_str.split('.')[1].rstrip('0'))
        else:
            decimal_places = 0
        
        # 使用quantize确保正确的小数位数
        if decimal_places > 0:
            quantizer = Decimal('0.1') ** decimal_places
            formatted_quantity = formatted_quantity.quantize(quantizer)
        else:
            formatted_quantity = formatted_quantity.quantize(Decimal('1'))
        
        # 转换为字符串
        return str(formatted_quantity)
    
    async def get_account_info(self) -> AccountInfo:
        """
        获取账户信息
        
        Returns:
            AccountInfo对象
        """
        try:
            response = await self.sdk_client.get_account_asset()
            data = response.get("data", {})
            
            # 解析账户余额（从collateralAssetModelList获取）
            collateral_list = data.get("collateralAssetModelList", [])
            if collateral_list:
                collateral_asset = collateral_list[0]  # 获取第一个币种（通常是USDT）
                balance = float(collateral_asset.get("totalEquity", 0))
                available_balance = float(collateral_asset.get("availableAmount", 0))
                margin_used = float(collateral_asset.get("orderFrozenAmount", 0))
                
                # 从positionAssetList计算未实现盈亏
                position_assets = data.get("positionAssetList", [])
                unrealized_pnl = sum(float(p.get("unrealizePnl", 0)) for p in position_assets)
            else:
                balance = 0
                available_balance = 0
                margin_used = 0
                unrealized_pnl = 0
            
            # 解析持仓（从positionList获取，不是positionAssetList）
            positions = {}
            position_list = data.get("positionList", [])
            
            for pos_data in position_list:
                contract_id = pos_data.get("contractId", "")
                symbol = self._get_symbol_by_contract_id(contract_id)
                
                if not symbol:
                    continue
                
                size = float(pos_data.get("size", 0))
                if abs(size) < 1e-8:  # 忽略零持仓
                    continue
                
                direction = TradeDirection.LONG if size > 0 else TradeDirection.SHORT
                
                position = Position(
                    symbol=symbol,
                    contract_id=contract_id,
                    direction=direction,
                    size=abs(size),
                    entry_price=float(pos_data.get("averageOpenPrice", 0)),
                    current_price=float(pos_data.get("markPrice", 0)),
                    unrealized_pnl=float(pos_data.get("unrealizedProfitAndLoss", 0)),
                    leverage=int(pos_data.get("leverage", 1)),
                    margin=float(pos_data.get("positionMargin", 0))
                )
                
                positions[symbol] = position
            
            return AccountInfo(
                balance=balance,
                available_balance=available_balance,
                margin_used=margin_used,
                unrealized_pnl=unrealized_pnl,
                positions=positions
            )
            
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            raise
    
    async def get_ticker(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """
        获取行情数据
        
        Args:
            contract_id: 合约ID
            
        Returns:
            行情数据字典
        """
        try:
            response = await self.sdk_client.get_24_hour_quote(contract_id)
            data_list = response.get("data", [])
            if data_list:
                return data_list[0]
            return None
        except Exception as e:
            logger.error(f"获取行情失败 {contract_id}: {e}")
            return None
    
    async def get_order_book(self, contract_id: str, depth: int = 15) -> Optional[OrderBook]:
        """
        获取订单簿
        
        Args:
            contract_id: 合约ID
            depth: 深度（15或200）
            
        Returns:
            OrderBook对象
        """
        try:
            params = GetOrderBookDepthParams(contract_id=contract_id, limit=depth)
            response = await self.sdk_client.quote.get_order_book_depth(params)
            
            # data是一个列表，取第一个元素
            data_list = response.get("data", [])
            if not data_list or len(data_list) == 0:
                return None
                
            data = data_list[0]
            symbol = self._get_symbol_by_contract_id(contract_id)
            
            if not symbol:
                return None
            
            # 解析买单 - 每项是字典格式 {"price": "...", "size": "..."}
            bids = []
            for bid_data in data.get("bids", []):
                if isinstance(bid_data, dict):
                    bids.append(OrderBookLevel(
                        price=float(bid_data.get("price", 0)),
                        quantity=float(bid_data.get("size", 0))
                    ))
            
            # 解析卖单 - 每项是字典格式 {"price": "...", "size": "..."}
            asks = []
            for ask_data in data.get("asks", []):
                if isinstance(ask_data, dict):
                    asks.append(OrderBookLevel(
                        price=float(ask_data.get("price", 0)),
                        quantity=float(ask_data.get("size", 0))
                    ))
            
            import time
            return OrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=int(time.time() * 1000)
            )
            
        except Exception as e:
            logger.error(f"获取订单簿失败 {contract_id}: {e}")
            return None
    
    async def place_order(self, order: Order) -> Optional[Dict[str, Any]]:
        """
        下单
        
        Args:
            order: 订单对象
            
        Returns:
            订单响应
        """
        try:
            contract_id = await self.get_contract_id_by_symbol(order.symbol)
            if not contract_id:
                logger.error(f"未找到合约ID: {order.symbol}")
                return None
            
            # 转换订单类型
            if order.order_type == OrderType.LIMIT or order.order_type == OrderType.POST_ONLY:
                sdk_order_type = SDKOrderType.LIMIT
                time_in_force = TimeInForce.POST_ONLY if order.order_type == OrderType.POST_ONLY else TimeInForce.GOOD_TIL_CANCEL
            else:
                sdk_order_type = SDKOrderType.MARKET
                time_in_force = TimeInForce.IMMEDIATE_OR_CANCEL
            
            # 格式化价格和数量
            formatted_price = self.format_price(contract_id, order.price) if order.price and order.price > 0 else "0"
            formatted_quantity = self.format_quantity(contract_id, order.quantity)
            
            # 创建订单参数
            params = CreateOrderParams(
                contract_id=contract_id,
                size=formatted_quantity,
                price=formatted_price,
                type=sdk_order_type,
                side=order.side,
                time_in_force=time_in_force,
                client_order_id=order.client_order_id if order.client_order_id else None
            )
            
            # 下单
            response = await self.sdk_client.create_order(params)
            
            if response.get("code") == "SUCCESS":
                logger.info(f"下单成功: {order.symbol} {order.side} {order.quantity}@{order.price}")
                return response
            else:
                logger.error(f"下单失败: {response.get('errorParam', response.get('code'))}")
                return None
                
        except Exception as e:
            logger.error(f"下单异常: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否成功
        """
        try:
            params = CancelOrderParams(order_id=order_id)
            response = await self.sdk_client.cancel_order(params)
            
            if response.get("code") == "SUCCESS":
                logger.info(f"取消订单成功: {order_id}")
                return True
            else:
                logger.error(f"取消订单失败: {response.get('errorParam', response.get('code'))}")
                return False
                
        except Exception as e:
            logger.error(f"取消订单异常: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        """
        取消所有订单
        
        Args:
            symbol: 交易对（可选，不指定则取消所有）
            
        Returns:
            是否成功
        """
        try:
            if symbol:
                contract_id = await self.get_contract_id_by_symbol(symbol)
                if not contract_id:
                    logger.error(f"未找到合约ID: {symbol}")
                    return False
                params = CancelOrderParams(contract_id=contract_id)
            else:
                params = CancelOrderParams(contract_id="")
            
            response = await self.sdk_client.cancel_order(params)
            
            if response.get("code") == "SUCCESS":
                logger.info(f"取消所有订单成功: {symbol or '全部'}")
                return True
            else:
                logger.error(f"取消所有订单失败: {response.get('errorParam', response.get('code'))}")
                return False
                
        except Exception as e:
            logger.error(f"取消所有订单异常: {e}")
            return False
    
    async def get_active_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取活跃订单
        
        Args:
            symbol: 交易对（可选）
            
        Returns:
            订单列表
        """
        try:
            params = GetActiveOrderParams()
            
            if symbol:
                contract_id = await self.get_contract_id_by_symbol(symbol)
                if contract_id:
                    params.filter_contract_id_list = [contract_id]
            
            response = await self.sdk_client.get_active_orders(params)
            
            if response.get("code") == "SUCCESS":
                return response.get("data", {}).get("list", [])
            else:
                logger.error(f"获取活跃订单失败: {response.get('errorParam', response.get('code'))}")
                return []
                
        except Exception as e:
            logger.error(f"获取活跃订单异常: {e}")
            return []
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        设置杠杆
        
        Args:
            symbol: 交易对
            leverage: 杠杆倍数
            
        Returns:
            是否成功
        """
        # EdgeX SDK暂未实现此功能，返回True
        logger.info(f"设置杠杆 {symbol}: {leverage}x")
        return True
    
    def _get_symbol_by_contract_id(self, contract_id: str) -> Optional[str]:
        """通过合约ID获取交易对名称"""
        for symbol, cid in self.symbol_to_contract_id.items():
            if cid == contract_id:
                return symbol
        return None
    
    async def close(self):
        """关闭客户端"""
        try:
            await self.sdk_client.close()
        except:
            pass

