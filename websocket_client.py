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
        max_retries = 5
        retry_delay = 5  # 5秒重试间隔
        
        for attempt in range(max_retries):
            try:
                # 连接公共WebSocket
                self.ws_manager.connect_public()
                self.running = True
                
                logger.info("WebSocket连接已建立")
                
                # 订阅所有交易对的ticker数据
                for symbol in self.symbols:
                    contract_id = self.contract_ids.get(symbol)
                    if contract_id:
                        # 订阅ticker数据
                        self.ws_manager.subscribe_ticker(
                            contract_id=contract_id,
                            handler=lambda msg, sym=symbol: self._handle_ticker_message(sym, msg)
                        )
                        logger.info(f"已订阅 {symbol} ({contract_id}) 的ticker数据")
                
                # 连接成功，跳出重试循环
                break
                
            except Exception as e:
                logger.warning(f"WebSocket连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"WebSocket连接失败，已达到最大重试次数 ({max_retries})")
                    raise
    
    async def stop(self):
        """停止WebSocket连接"""
        self.running = False
        if self.ws_manager:
            self.ws_manager.disconnect_all()
        logger.info("WebSocket连接已关闭")
    
    def _handle_ticker_message(self, symbol: str, message: str):
        """处理ticker消息"""
        try:
            data = json.loads(message)
            
            # 解析ticker数据
            if "data" in data:
                ticker_data = data["data"]
                price = self._parse_ticker_data(ticker_data)
                
                if price:
                    # 添加到历史记录
                    self.price_history[symbol].append(price)
                    
                    # 保持历史记录在合理范围内
                    if len(self.price_history[symbol]) > 1000:
                        self.price_history[symbol] = self.price_history[symbol][-1000:]
                    
                    # 调用回调函数
                    for callback in self.price_callbacks:
                        try:
                            callback(symbol, price)
                        except Exception as e:
                            logger.error(f"价格回调函数执行失败: {e}")
                    
                    logger.debug(f"{symbol}: 价格更新 {price.close}")
        
        except Exception as e:
            logger.error(f"处理ticker消息失败: {e}")
    
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
