#!/usr/bin/env python3
"""
测试K线API
"""

import asyncio
from loguru import logger
from config import load_config
from edgex_client import EdgeXClient

async def test_kline_api():
    """测试K线API获取"""
    logger.info("="*60)
    logger.info("测试K线API")
    logger.info("="*60)
    
    try:
        config = load_config()
        client = EdgeXClient(config)
        
        # 等待缓存初始化
        await asyncio.sleep(2)
        
        # 测试不同的交易对
        test_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        
        for symbol in test_symbols:
            logger.info(f"\n测试 {symbol}:")
            
            # 1. 获取合约ID
            contract_id = await client.get_contract_id_by_symbol(symbol)
            logger.info(f"  合约ID: {contract_id}")
            
            if not contract_id:
                logger.error(f"  ❌ 无法找到合约ID")
                continue
            
            # 2. 直接使用合约ID获取K线
            try:
                logger.info(f"  尝试获取K线（使用合约ID: {contract_id}）...")
                klines = await client.get_klines(
                    symbol=contract_id,
                    interval="1m",
                    limit=10
                )
                
                if klines:
                    logger.info(f"  ✅ 成功获取 {len(klines)} 根K线")
                    logger.info(f"  最新价格: {klines[-1].close}")
                    logger.info(f"  时间戳: {klines[-1].timestamp}")
                else:
                    logger.warning(f"  ⚠️ 返回空K线列表")
                    
            except Exception as e:
                logger.error(f"  ❌ 获取K线失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # 3. 使用交易对名称获取（测试自动转换）
            try:
                logger.info(f"  尝试获取K线（使用交易对名称: {symbol}）...")
                klines2 = await client.get_klines(
                    symbol=symbol,  # 直接使用交易对名称
                    interval="1m",
                    limit=10
                )
                
                if klines2:
                    logger.info(f"  ✅ 成功获取 {len(klines2)} 根K线（自动转换）")
                else:
                    logger.warning(f"  ⚠️ 返回空K线列表")
                    
            except Exception as e:
                logger.error(f"  ❌ 自动转换失败: {e}")
        
        await client.close()
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_kline_api())

