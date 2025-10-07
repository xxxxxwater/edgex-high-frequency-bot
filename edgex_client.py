"""
EdgeX API客户端
使用官方edgex-python-sdk
"""

import asyncio
import sys
import os
from typing import List, Optional, Dict, Any
from loguru import logger

# 添加SDK路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sdk'))

try:
    from edgex_sdk import (
        Client as EdgeXSDKClient,
        OrderSide as SDKOrderSide,
        OrderType as SDKOrderType,
        CreateOrderParams,
        CancelOrderParams,
        GetActiveOrderParams,
        GetKLineParams
    )
except ImportError as e:
    logger.error(f"导入edgex_sdk失败: {e}")
    logger.error("请确保SDK已正确安装在sdk/edgex_sdk目录")
    raise

from edgex_types import AccountInfo, PriceData, Order, OrderSide, OrderType, Position, TradeDirection


class EdgeXClient:
    """EdgeX API客户端封装"""
    
    # 合约ID映射缓存（类级别，所有实例共享）
    _contract_id_cache: Dict[str, str] = {}
    _cache_initialized: bool = False
    
    def __init__(self, config):
        """
        初始化客户端
        
        Args:
            config: 配置对象，包含API密钥、账户ID等信息
        """
        self.config = config
        self.sdk_client: Optional[EdgeXSDKClient] = None
        self._initialize_sdk()
    
    def _initialize_sdk(self):
        """初始化SDK客户端"""
        try:
            # 确定base_url
            if self.config.testnet:
                base_url = "https://testnet.edgex.exchange"
            else:
                base_url = "https://pro.edgex.exchange"
            
            logger.info(f"初始化EdgeX SDK: {base_url}")
            
            # 创建SDK客户端（不使用async context manager）
            self.sdk_client = EdgeXSDKClient(
                base_url=base_url,
                account_id=int(self.config.account_id) if self.config.account_id else 0,
                stark_private_key=self.config.stark_private_key or ""
            )
            
            logger.info("EdgeX SDK初始化成功")
            
            # 异步初始化合约ID缓存（不等待完成）
            asyncio.create_task(self._init_contract_cache())
            
        except Exception as e:
            logger.error(f"EdgeX SDK初始化失败: {e}")
            raise
    
    async def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        try:
            # 获取账户资产
            asset_response = await self.sdk_client.account.get_account_asset()
            
            if not asset_response or asset_response.get("code") != "SUCCESS":
                raise ValueError(f"获取账户资产失败: {asset_response}")
            
            asset_data = asset_response.get("data", {})
            
            # 解析余额
            balance = float(asset_data.get("totalEquity", 0))
            available_balance = float(asset_data.get("availableBalance", 0))
            
            # 获取持仓信息
            positions = {}
            positions_response = await self.sdk_client.account.get_account_positions()
            
            if positions_response and positions_response.get("code") == "SUCCESS":
                position_list = positions_response.get("data", {}).get("positionList", [])
                
                for pos_data in position_list:
                    contract_id = pos_data.get("contractId", "")
                    if not contract_id:
                        continue
                    
                    # 解析方向
                    position_side = pos_data.get("positionSide", "LONG")
                    if position_side == "LONG":
                        direction = TradeDirection.LONG
                    elif position_side == "SHORT":
                        direction = TradeDirection.SHORT
                    else:
                        continue
                    
                    # 解析持仓大小（可能是负数表示方向）
                    size = abs(float(pos_data.get("positionSize", 0)))
                    
                    if size > 0:  # 只记录有持仓的
                        position = Position(
                            symbol=contract_id,
                            direction=direction,
                            size=size,
                            entry_price=float(pos_data.get("avgEntryPrice", 0)),
                            stop_loss=0.0,  # SDK不直接提供，需要从订单中获取
                            take_profit=0.0,  # SDK不直接提供，需要从订单中获取
                            leverage=int(pos_data.get("leverage", 1)),
                            opening_time=int(pos_data.get("createdTime", 0))
                        )
                        positions[contract_id] = position
            
            return AccountInfo(
                balance=balance,
                available_balance=available_balance,
                positions=positions
            )
            
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            raise
    
    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[PriceData]:
        """
        获取K线数据
        
        Args:
            symbol: 合约ID（如"10000003"表示SOL-USDT）
            interval: 时间间隔（如"1m", "5m", "1h"）
            limit: 数量限制
            
        Returns:
            List[PriceData]: K线数据列表
        """
        try:
            # 映射interval格式
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "1h": "1h",
                "4h": "4h",
                "1d": "1d"
            }
            
            sdk_interval = interval_map.get(interval, "1m")
            
            # 创建K线参数
            params = GetKLineParams(
                contract_id=symbol,
                interval=sdk_interval,
                size=str(limit)
            )
            
            # 获取K线数据
            response = await self.sdk_client.quote.get_k_line(params)
            
            if not response or response.get("code") != "SUCCESS":
                raise ValueError(f"获取K线数据失败: {response}")
            
            kline_list = response.get("data", {}).get("dataList", [])
            
            # 转换为PriceData格式
            price_data_list = []
            for kline in kline_list:
                price_data = PriceData(
                    timestamp=int(kline.get("timestamp", 0)),
                    open=float(kline.get("open", 0)),
                    high=float(kline.get("high", 0)),
                    low=float(kline.get("low", 0)),
                    close=float(kline.get("close", 0)),
                    volume=float(kline.get("volume", 0))
                )
                price_data_list.append(price_data)
            
            return price_data_list
            
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            raise
    
    async def place_order(self, order: Order) -> Dict[str, Any]:
        """
        下单
        
        Args:
            order: 订单对象
            
        Returns:
            Dict[str, Any]: 下单响应
        """
        try:
            # 转换OrderSide
            if order.side == OrderSide.BUY:
                sdk_side = SDKOrderSide.BUY
            else:
                sdk_side = SDKOrderSide.SELL
            
            # 转换OrderType
            if order.order_type == OrderType.MARKET:
                sdk_type = SDKOrderType.MARKET
            else:
                sdk_type = SDKOrderType.LIMIT
            
            # 创建订单参数
            params = CreateOrderParams(
                contract_id=order.symbol,
                price=str(order.price) if order.price else "0",
                size=str(order.quantity),
                type=sdk_type,
                side=sdk_side.value,
                reduce_only=False
            )
            
            # 下单
            response = await self.sdk_client.create_order(params)
            
            if not response or response.get("code") != "SUCCESS":
                error_msg = response.get("errorParam", {}).get("message", "未知错误")
                raise ValueError(f"下单失败: {error_msg}")
            
            logger.info(f"订单提交成功: {order.symbol} {order.side.value} {order.quantity}")
            return response
            
        except Exception as e:
            logger.error(f"下单失败: {e}")
            raise
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        设置杠杆
        
        注意: EdgeX的杠杆设置可能需要通过其他API或在下单时指定
        这里提供一个占位实现
        
        Args:
            symbol: 合约ID
            leverage: 杠杆倍数
            
        Returns:
            Dict[str, Any]: 设置响应
        """
        try:
            logger.info(f"设置杠杆: {symbol} {leverage}x")
            logger.warning("EdgeX SDK暂不支持单独设置杠杆，杠杆在账户级别配置")
            
            return {
                "code": "SUCCESS",
                "data": {
                    "symbol": symbol,
                    "leverage": leverage
                }
            }
            
        except Exception as e:
            logger.error(f"设置杠杆失败: {e}")
            raise
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            symbol: 合约ID
            order_id: 订单ID
            
        Returns:
            Dict[str, Any]: 取消响应
        """
        try:
            params = CancelOrderParams(
                order_id=order_id
            )
            
            response = await self.sdk_client.cancel_order(params)
            
            if not response or response.get("code") != "SUCCESS":
                raise ValueError(f"取消订单失败: {response}")
            
            logger.info(f"取消订单成功: {symbol} {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            raise
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取未成交订单
        
        Args:
            symbol: 可选的合约ID筛选
            
        Returns:
            List[Dict[str, Any]]: 订单列表
        """
        try:
            params = GetActiveOrderParams(
                size="100",
                offset_data=""
            )
            
            # 如果指定了symbol，添加筛选
            if symbol:
                params.filter_contract_id_list = [symbol]
            
            response = await self.sdk_client.get_active_orders(params)
            
            if not response or response.get("code") != "SUCCESS":
                raise ValueError(f"获取未成交订单失败: {response}")
            
            order_list = response.get("data", {}).get("dataList", [])
            return order_list
            
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            raise
    
    async def get_ticker(self, contract_id: str) -> Dict[str, Any]:
        """
        获取ticker数据
        
        Args:
            contract_id: 合约ID（如"10000003"表示SOL-USDT）
            
        Returns:
            Dict[str, Any]: ticker数据
        """
        try:
            response = await self.sdk_client.quote.get_24_hour_quote(contract_id)
            
            if not response or response.get("code") != "SUCCESS":
                raise ValueError(f"获取ticker失败: {response}")
            
            # 返回第一个ticker数据
            ticker_list = response.get("data", [])
            if ticker_list and len(ticker_list) > 0:
                return ticker_list[0]
            else:
                raise ValueError("ticker数据为空")
            
        except Exception as e:
            logger.error(f"获取ticker失败: {e}")
            raise
    
    async def _init_contract_cache(self):
        """初始化合约ID缓存"""
        if EdgeXClient._cache_initialized:
            return
        
        try:
            metadata = await self.sdk_client.get_metadata()
            
            if not metadata or metadata.get("code") != "SUCCESS":
                logger.warning("获取元数据失败，合约ID缓存未初始化")
                return
            
            contracts = metadata.get("data", {}).get("contractList", [])
            
            for contract in contracts:
                contract_name = contract.get("contractName")
                contract_id = contract.get("contractId")
                if contract_name and contract_id:
                    EdgeXClient._contract_id_cache[contract_name] = contract_id
                    # 同时添加反向映射
                    EdgeXClient._contract_id_cache[contract_id] = contract_id
            
            EdgeXClient._cache_initialized = True
            logger.info(f"合约ID缓存初始化完成，共 {len(EdgeXClient._contract_id_cache)} 个映射")
            
            # 调试：显示前10个映射
            logger.debug("合约ID映射示例:")
            count = 0
            for symbol, cid in EdgeXClient._contract_id_cache.items():
                if not symbol.isdigit() and count < 10:
                    logger.debug(f"  {symbol} -> {cid}")
                    count += 1
            
        except Exception as e:
            logger.error(f"初始化合约ID缓存失败: {e}")
    
    async def get_contract_id_by_symbol(self, symbol_name: str) -> Optional[str]:
        """
        根据交易对名称获取合约ID（带缓存）
        
        Args:
            symbol_name: 交易对名称（如"SOL-USDT"）或合约ID（如"10000003"）
            
        Returns:
            Optional[str]: 合约ID（如"10000003"）
        """
        # 如果已经是数字ID，直接返回
        if symbol_name.isdigit():
            return symbol_name
        
        # 初始化缓存
        if not EdgeXClient._cache_initialized:
            await self._init_contract_cache()
        
        # 从缓存查找
        if symbol_name in EdgeXClient._contract_id_cache:
            return EdgeXClient._contract_id_cache[symbol_name]
        
        # 尝试映射常见的交易对格式
        symbol_mapping = {
            "BTC-USDT": "BTCUSD",
            "ETH-USDT": "ETHUSD", 
            "SOL-USDT": "SOLUSD",
            "BNB-USDT": "BNB2USD",
            "LTC-USDT": "LTC2USD",
            "LINK-USDT": "LINK2USD",
            "AVAX-USDT": "AVAX2USD",
            "MATIC-USDT": "MATICUSD",
            "XRP-USDT": "XRP2USD",
            "DOGE-USDT": "DOGE2USD"
        }
        
        # 尝试映射后的名称
        mapped_symbol = symbol_mapping.get(symbol_name)
        if mapped_symbol and mapped_symbol in EdgeXClient._contract_id_cache:
            return EdgeXClient._contract_id_cache[mapped_symbol]
        
        # 调试：显示可用的交易对
        logger.debug(f"查找交易对 {symbol_name}，可用交易对:")
        count = 0
        for symbol in EdgeXClient._contract_id_cache.keys():
            if not symbol.isdigit() and count < 10:
                logger.debug(f"  {symbol}")
                count += 1
        
        logger.warning(f"未找到交易对 {symbol_name} 的合约ID")
        return None
    
    def get_symbol_by_contract_id(self, contract_id: str) -> str:
        """
        根据合约ID获取交易对名称
        
        Args:
            contract_id: 合约ID（如"10000003"）
            
        Returns:
            str: 交易对名称（如"SOL-USDT"）或原始contract_id
        """
        # 反向查找
        for symbol, cid in EdgeXClient._contract_id_cache.items():
            if cid == contract_id and not symbol.isdigit():
                return symbol
        return contract_id
    
    async def close(self):
        """关闭客户端"""
        if self.sdk_client:
            await self.sdk_client.close()
            logger.info("EdgeX客户端已关闭")
