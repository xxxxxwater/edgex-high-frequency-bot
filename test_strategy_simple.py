#!/usr/bin/env python3
"""
简化的策略测试
"""

import asyncio
from loguru import logger
from config import load_config
from strategy import HighFrequencyStrategy

async def test_strategy():
    """测试策略执行"""
    logger.info("="*60)
    logger.info("测试策略执行")
    logger.info("="*60)
    
    config = load_config()
    strategy = HighFrequencyStrategy(config)
    
    # 更新账户信息
    try:
        await strategy._update_account_info()
        logger.info(f"账户余额: {strategy.balance}")
    except Exception as e:
        logger.warning(f"账户信息获取失败: {e}")
    
    # 初始化WebSocket
    try:
        await strategy._initialize_websocket()
    except Exception as e:
        logger.warning(f"WebSocket初始化失败: {e}")
    
    # 测试5个周期的策略执行
    for i in range(5):
        logger.info(f"\n====== 周期 {i+1} ======")
        for symbol in config.symbols[:2]:  # 只测试前2个交易对
            await strategy._execute_strategy_for_symbol(symbol)
            logger.info(f"{symbol}: 历史数据长度 = {len(strategy.price_history.get(symbol, []))}")
        await asyncio.sleep(2)
    
    logger.info("\n测试完成")

if __name__ == "__main__":
    asyncio.run(test_strategy())

