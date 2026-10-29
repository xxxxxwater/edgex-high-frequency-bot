"""
EdgeX WebSocket客户端
使用EdgeX SDK的WebSocket实现
"""

import asyncio
import json
import time
from typing import Dict, List, Callable, Optional
from loguru import logger
from edgex_types import PriceData
from sdk.edgex_sdk.ws.manager import Manager as WebSocketManager
from sdk.edgex_sdk.internal.starkex_signing_adapter import StarkExSigningAdapter


class RealTimePriceStream:
    """实时价格数据流"""
    
    def __init__(self, symbols: List[str], contract_ids: Dict[str, str], 
                 base_url: str, account_id: int, stark_private_key: str):
        """
        初始化价格流
        
        Args:
            symbols: 交易对列表
            contract_ids: 交易对到合约ID的映射
            base_url: EdgeX API基础URL
            account_id: 账户ID
            stark_private_key: Stark私钥
        """
        self.symbols = symbols
        self.contract_ids = contract_ids
        self._disconnect_hook_registered = False
        self.running = False
        self.price_callbacks: List[Callable[[str, PriceData], None]] = []
        self.price_history: Dict[str, List[PriceData]] = {}
        
        # 创建WebSocket管理器
        self.ws_manager = WebSocketManager(
            base_url=base_url,
            account_id=account_id,
            stark_pri_key=stark_private_key,
            signing_adapter=StarkExSigningAdapter()
        )
        
        # 为每个交易对初始化价格历史
        for symbol in symbols:
            self.price_history[symbol] = []
    
    def add_price_callback(self, callback: Callable[[str, PriceData], None]):
        """添加价格数据回调函数"""
        self.price_callbacks.append(callback)
    
    async def start(self):
        """启动WebSocket连接（带重试机制）"""
        max_retries = 3
        retry_delay = 3  # 3秒重试间隔
        
        # SDK 客户端断线后不会自动重连；这里至少记录错误，
        # 策略侧在价格超过 5 秒未更新时会自动改用 REST ticker
        if not self._disconnect_hook_registered:
            self.ws_manager.get_public_client().on_disconnect(
                lambda e: logger.error(f"❌ WebSocket连接已断开，将改用REST获取价格: {e}")
            )
            self._disconnect_hook_registered = True
        
        for attempt in range(max_retries):
            try:
                # 连接公共WebSocket
                logger.info(f"尝试连接WebSocket (第 {attempt + 1}/{max_retries} 次)...")
                self.ws_manager.connect_public()
                self.running = True
                
                logger.info("✅ WebSocket连接已建立")
                
                # 等待连接稳定
                await asyncio.sleep(1)
                
                # 订阅所有交易对的ticker数据
                subscribed_count = 0
                for symbol in self.symbols:
                    contract_id = self.contract_ids.get(symbol)
                    if contract_id:
                        try:
                            # 订阅ticker数据。SDK 按消息类型 "ticker" 只保存一个 handler，
                            # 每次订阅都会覆盖上一个，所以统一用按 channel 分发的 handler
                            self.ws_manager.subscribe_ticker(
                                contract_id=contract_id,
                                handler=self._dispatch_ticker_message
                            )
                            logger.info(f"✅ 已订阅 {symbol} ({contract_id}) 的ticker数据")
                            subscribed_count += 1
                        except Exception as sub_error:
                            logger.warning(f"订阅 {symbol} 失败: {sub_error}")
                
                if subscribed_count == 0:
                    raise ValueError("没有成功订阅任何交易对")
                
                logger.info(f"✅ 成功订阅 {subscribed_count}/{len(self.symbols)} 个交易对")
                
                # 连接成功，跳出重试循环
                break
                
            except Exception as e:
                logger.warning(f"⚠️ WebSocket连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                
                # 清理连接
                try:
                    if self.ws_manager:
                        self.ws_manager.disconnect_public()
                except:
                    pass
                
                if attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"❌ WebSocket连接失败，已达到最大重试次数 ({max_retries})")
                    raise
    
    async def stop(self):
        """停止WebSocket连接"""
        self.running = False
        if self.ws_manager:
            self.ws_manager.disconnect_all()
        logger.info("WebSocket连接已关闭")
    
    def _dispatch_ticker_message(self, message: str):
        """
        按消息 channel（"ticker.<合约ID>"）或数据中的 contractId 把 ticker 分发到对应交易对
        
        之前每个交易对注册一个 lambda handler，但 SDK 的 on_message("ticker", handler)
        是按消息类型覆盖保存的，最终只剩最后一个交易对的 handler：
        所有币种的 ticker 都被记到最后一个交易对的价格历史里（例如 BTC 的价格被当成 BNB），
        直接导致错误的均线偏离信号和止盈止损判断。
        """
        try:
            data = json.loads(message)
        except Exception as e:
            logger.error(f"处理ticker消息失败: {e}")
            return
        
        channel = data.get("channel") or (data.get("content") or {}).get("channel") or ""
        channel_contract = channel.split(".", 1)[1] if "." in channel else None
        symbol_by_contract = {str(cid): sym for sym, cid in self.contract_ids.items()}
        
        for item in self._extract_ticker_items(data):
            contract_id = str(item.get("contractId") or channel_contract or "")
            symbol = symbol_by_contract.get(contract_id)
            if symbol is None:
                logger.debug(f"忽略未订阅合约的ticker: {contract_id}")
                continue
            self._on_ticker(symbol, item)
    
    def _handle_ticker_message(self, symbol: str, message: str):
        """处理指定交易对的ticker消息"""
        try:
            data = json.loads(message)
            for item in self._extract_ticker_items(data):
                self._on_ticker(symbol, item)
        except Exception as e:
            logger.error(f"处理ticker消息失败: {e}")
    
    @staticmethod
    def _extract_ticker_items(data: dict) -> List[dict]:
        """
        取出消息中的 ticker 数据，兼容 {"data": {...}} 与
        {"content": {"data": [...]}} 两种结构（data 可能是对象或列表）
        """
        payload = data.get("data")
        if payload is None and isinstance(data.get("content"), dict):
            payload = data["content"].get("data")
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []
    
    def _on_ticker(self, symbol: str, ticker_data: dict):
        price = self._parse_ticker_data(ticker_data)
        if not price:
            return
        
        # 添加到历史记录
        history = self.price_history.setdefault(symbol, [])
        history.append(price)
        
        # 保持历史记录在合理范围内
        if len(history) > 1000:
            self.price_history[symbol] = history[-1000:]
        
        # 调用回调函数
        for callback in self.price_callbacks:
            try:
                callback(symbol, price)
            except Exception as e:
                logger.error(f"价格回调函数执行失败: {e}")
        
        logger.debug(f"{symbol}: 价格更新 {price.close}")
    
    def _parse_ticker_data(self, data: dict) -> Optional[PriceData]:
        """解析ticker数据为PriceData格式"""
        try:
            # 从ticker数据中提取价格信息
            current_price = float(data.get("lastPrice", 0))  # 当前价格
            open_price = float(data.get("open", current_price))  # 开盘价
            high_price = float(data.get("high", current_price))  # 最高价
            low_price = float(data.get("low", current_price))   # 最低价
            volume = float(data.get("size", 0))  # 成交量
            timestamp = int(data.get("timestamp", time.time() * 1000))  # 时间戳
            
            if current_price <= 0:
                return None
            
            return PriceData(
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=current_price,
                volume=volume
            )
        except Exception as e:
            logger.error(f"解析ticker数据失败: {e}")
            return None
    
    def get_price_history(self, symbol: str, limit: int = 100) -> List[PriceData]:
        """获取指定交易对的价格历史"""
        history = self.price_history.get(symbol, [])
        return history[-limit:] if history else []
    
    def get_latest_price(self, symbol: str) -> Optional[PriceData]:
        """获取指定交易对的最新价格"""
        history = self.price_history.get(symbol, [])
        return history[-1] if history else None
