"""
EdgeX API客户端
使用官方edgex-python-sdk
"""

import asyncio
import sys
import os
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
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
        """
        获取账户信息
        
        字段结构以官方 SDK 为准（edgex-golang-sdk sdk/account/types.go 的 AccountAssetData）：
        - 余额在 data.collateralAssetModelList[].totalEquity / availableBalance；
        - 持仓在 data.positionList[]，openSize 为带符号的持仓数量（正=多，负=空），
          openValue 为开仓价值，没有 positionSide / positionSize / avgEntryPrice 字段。
        之前按 data.totalEquity、positionSize 解析：余额恒为 0、持仓恒为空。
        
        响应缺少关键字段时直接抛出异常（策略会暂停本轮交易），
        而不是当作"余额 0 / 无持仓"处理——后者会让策略在已有持仓时继续开仓。
        """
        try:
            # getAccountAsset 同时返回余额和持仓（SDK 的 get_account_positions 调用的是同一个接口）
            asset_response = await self.sdk_client.account.get_account_asset()
            
            if not asset_response or asset_response.get("code") != "SUCCESS":
                raise ValueError(f"获取账户资产失败: {asset_response}")
            
            asset_data = asset_response.get("data") or {}
            balance, available_balance = self._parse_balances(asset_data)
            positions = self._parse_positions(asset_data)
            
            return AccountInfo(
                balance=balance,
                available_balance=available_balance,
                positions=positions
            )
            
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            raise
    
    @staticmethod
    def _parse_balances(asset_data: Dict[str, Any]):
        collateral_list = asset_data.get("collateralAssetModelList")
        if collateral_list:
            collateral = collateral_list[0]
        elif "totalEquity" in asset_data:
            collateral = asset_data
        else:
            raise ValueError("账户资产响应缺少 collateralAssetModelList，无法确定余额")
        
        equity = collateral.get("totalEquity")
        available = collateral.get("availableBalance", collateral.get("availableAmount"))
        if equity is None or available is None:
            raise ValueError(f"账户资产响应缺少 totalEquity/availableBalance: {collateral}")
        return float(equity), float(available)
    
    def _parse_positions(self, asset_data: Dict[str, Any]) -> Dict[str, Position]:
        positions = {}
        for pos_data in asset_data.get("positionList") or []:
            contract_id = str(pos_data.get("contractId") or "")
            if not contract_id:
                continue
            
            raw_size = pos_data.get("openSize", pos_data.get("size"))
            if raw_size is None:
                raise ValueError(f"持仓数据缺少 openSize，无法确认持仓: {pos_data}")
            size = Decimal(str(raw_size))
            if size == 0:
                continue
            
            direction = TradeDirection.LONG if size > 0 else TradeDirection.SHORT
            open_value = abs(Decimal(str(pos_data.get("openValue") or "0")))
            entry_price = open_value / abs(size)
            
            created_ms = int(pos_data.get("createdTime") or 0)
            positions[contract_id] = Position(
                symbol=contract_id,
                direction=direction,
                size=float(abs(size)),
                entry_price=float(entry_price),
                stop_loss=0.0,  # 接口不提供，由策略按开仓均价计算
                take_profit=0.0,
                # 持仓接口不返回杠杆，使用配置值
                leverage=int(pos_data.get("leverage") or getattr(self.config, "leverage", 1)),
                opening_time=created_ms // 1000  # 毫秒 -> 秒（TradeRecord.duration 按秒计算）
            )
        return positions
    
    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[PriceData]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对名称（如"SOL-USDT"）或合约ID（如"10000003"）
            interval: 时间间隔（如"1m", "5m", "1h"）
            limit: 数量限制
            
        Returns:
            List[PriceData]: K线数据列表
        """
        try:
            # 如果是交易对名称，需要转换为合约ID
            contract_id = symbol
            if not symbol.isdigit():
                contract_id = await self.get_contract_id_by_symbol(symbol)
                if not contract_id:
                    raise ValueError(f"无法找到交易对 {symbol} 的合约ID")
            
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
                contract_id=contract_id,
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
            order: 订单对象（symbol 可以是交易对名称或合约ID）
            
        Returns:
            Dict[str, Any]: 下单响应
        """
        try:
            # 策略传入的是交易对名称（如 "SOL-USDT"），SDK 需要合约ID
            contract_id = await self.get_contract_id_by_symbol(order.symbol)
            if not contract_id:
                raise ValueError(f"无法找到交易对 {order.symbol} 的合约ID")
            
            metadata = await self.sdk_client.get_metadata()
            if not metadata or metadata.get("code") != "SUCCESS":
                raise ValueError(f"获取元数据失败: {metadata}")
            metadata_data = metadata.get("data", {})
            contract = self._find_contract(metadata_data, contract_id)
            
            # 转换OrderSide（SDK 内部使用 params.side.value，必须传枚举而不是字符串）
            sdk_side = SDKOrderSide.BUY if order.side == OrderSide.BUY else SDKOrderSide.SELL
            
            # 转换OrderType
            if order.order_type == OrderType.MARKET:
                sdk_type = SDKOrderType.MARKET
                price = await self._market_order_price(contract_id, sdk_side, contract)
            else:
                sdk_type = SDKOrderType.LIMIT
                if not order.price or order.price <= 0:
                    raise ValueError("限价单必须指定价格")
                price = self._format_price(order.price, contract)
            
            size = self._format_size(order.quantity, contract)
            
            # 创建订单参数
            params = CreateOrderParams(
                contract_id=contract_id,
                price=price,
                size=size,
                type=sdk_type,
                side=sdk_side,
                reduce_only=order.reduce_only
            )
            
            # 下单（元数据已获取，直接调用 order 客户端，避免重复请求）
            response = await self.sdk_client.order.create_order(params, metadata_data)
            
            if not response or response.get("code") != "SUCCESS":
                error_msg = (response or {}).get("errorParam", {}).get("message", "未知错误")
                raise ValueError(f"下单失败: {error_msg} ({response})")
            
            logger.info(
                f"订单提交成功: {order.symbol}({contract_id}) {order.side.value} {size}"
                f"{' reduceOnly' if order.reduce_only else ''}"
            )
            return response
            
        except Exception as e:
            logger.error(f"下单失败: {e}")
            raise
    
    @staticmethod
    def _find_contract(metadata_data: Dict[str, Any], contract_id: str) -> Dict[str, Any]:
        for contract in metadata_data.get("contractList", []):
            if contract.get("contractId") == contract_id:
                return contract
        raise ValueError(f"元数据中找不到合约 {contract_id}")
    
    @staticmethod
    def _format_size(quantity: float, contract: Dict[str, Any]) -> str:
        """
        按合约 stepSize 向下取整下单数量，并检查交易所最小下单量
        
        向下取整保证不会超出策略计算的数量；未对齐 stepSize 的数量会被交易所拒绝，
        float 运算产生的长尾小数（如 0.30000000000000004）也会在这里被截掉。
        """
        size = Decimal(str(quantity))
        if size <= 0:
            raise ValueError(f"下单数量必须大于0: {quantity}")
        
        step = Decimal(str(contract.get("stepSize") or "0"))
        if step > 0:
            size = (size / step).to_integral_value(rounding=ROUND_DOWN) * step
        
        min_size = Decimal(str(contract.get("minOrderSize") or "0"))
        if size <= 0 or size < min_size:
            raise ValueError(f"下单数量 {quantity} 按步长 {step} 取整后为 {size}，低于最小下单量 {min_size}")
        
        return format(size.normalize(), "f")
    
    @staticmethod
    def _format_price(price: float, contract: Dict[str, Any]) -> str:
        """按合约 tickSize 对齐价格"""
        value = Decimal(str(price))
        tick = Decimal(str(contract.get("tickSize") or "0"))
        if tick > 0:
            value = (value / tick).to_integral_value(rounding=ROUND_HALF_UP) * tick
        return format(value.normalize(), "f")
    
    async def _market_order_price(self, contract_id: str, side, contract: Dict[str, Any]) -> str:
        """
        市价单的签名价格（与 SDK create_market_order 保持一致）
        
        EdgeX 市价单仍需要用价格计算 l2Value / l2LimitFee 并签名。之前固定传 "0"，
        导致 l2Value=0、手续费上限=0，订单无法被交易所接受。
        买单使用 oraclePrice * 10（最差可接受价格），卖单使用 tickSize。
        """
        tick_size = contract.get("tickSize", "0")
        if side != SDKOrderSide.BUY:
            return tick_size
        
        quote = await self.sdk_client.get_24_hour_quote(contract_id)
        quote_list = (quote or {}).get("data") or []
        if not quote_list:
            raise ValueError(f"获取 {contract_id} 预言机价格失败: {quote}")
        oracle_price = Decimal(str(quote_list[0].get("oraclePrice") or "0"))
        if oracle_price <= 0:
            raise ValueError(f"{contract_id} 预言机价格无效: {oracle_price}")
        
        precision = abs(Decimal(str(tick_size)).as_tuple().exponent)
        return str(round(oracle_price * Decimal("10"), precision))
    
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
        
        # 从缓存查找（精确匹配）
        if symbol_name in EdgeXClient._contract_id_cache:
            return EdgeXClient._contract_id_cache[symbol_name]
        
        # 尝试映射常见的交易对格式
        # EdgeX的命名格式可能是: BTCUSD, ETHUSD, SOLUSD 等
        symbol_mappings = [
            # 格式1: BTC-USDT -> BTCUSD
            symbol_name.replace("-", "").replace("USDT", "USD"),
            # 格式2: BTC-USDT -> BTCUSDT
            symbol_name.replace("-", ""),
            # 格式3: BTC-USDT -> BTC2USD (某些币种)
            symbol_name.replace("-USDT", "2USD"),
            # 格式4: 去掉连字符
            symbol_name.replace("-", ""),
            # 格式5: 小写
            symbol_name.lower(),
            symbol_name.lower().replace("-", ""),
        ]
        
        # 尝试所有可能的映射格式
        for mapped_symbol in symbol_mappings:
            if mapped_symbol in EdgeXClient._contract_id_cache:
                logger.info(f"找到映射: {symbol_name} -> {mapped_symbol} -> {EdgeXClient._contract_id_cache[mapped_symbol]}")
                return EdgeXClient._contract_id_cache[mapped_symbol]
        
        # 模糊匹配：查找包含币种名称的合约
        base_currency = symbol_name.split("-")[0]  # 提取 BTC, ETH 等
        for cached_symbol, contract_id in EdgeXClient._contract_id_cache.items():
            if not cached_symbol.isdigit():
                # 检查是否包含币种名称
                if base_currency.upper() in cached_symbol.upper():
                    # 检查是否是USD交易对（排除其他交易对）
                    if "USD" in cached_symbol.upper():
                        logger.info(f"模糊匹配: {symbol_name} -> {cached_symbol} -> {contract_id}")
                        # 保存映射以便下次使用
                        EdgeXClient._contract_id_cache[symbol_name] = contract_id
                        return contract_id
        
        # 调试：显示可用的交易对
        logger.warning(f"未找到交易对 {symbol_name}，可用交易对:")
        count = 0
        for symbol in EdgeXClient._contract_id_cache.keys():
            if not symbol.isdigit() and count < 20:
                logger.warning(f"  {symbol}")
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
