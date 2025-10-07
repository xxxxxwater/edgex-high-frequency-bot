#!/usr/bin/env python3
"""
调试合约ID映射
"""

import asyncio
from loguru import logger
from config import load_config
from edgex_client import EdgeXClient

async def debug_contracts():
    """调试合约ID映射"""
    try:
        # 加载配置
        config = load_config()
        from config import validate_config
        validate_config(config)
        
        # 创建客户端
        client = EdgeXClient(config)
        
        # 等待缓存初始化
        await client._init_contract_cache()
        
        # 显示所有合约映射
        logger.info("=== 合约ID映射调试 ===")
        logger.info(f"缓存大小: {len(EdgeXClient._contract_id_cache)}")
        
        # 查找我们需要的交易对
        target_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"]
        
        for symbol in target_symbols:
            contract_id = await client.get_contract_id_by_symbol(symbol)
            logger.info(f"{symbol} -> {contract_id}")
        
        # 显示所有可用的交易对
        logger.info("\n=== 所有可用交易对 ===")
        count = 0
        for symbol, cid in EdgeXClient._contract_id_cache.items():
            if not symbol.isdigit():
                logger.info(f"{symbol} -> {cid}")
                count += 1
                if count > 20:  # 只显示前20个
                    break
        
        await client.close()
        
    except Exception as e:
        logger.error(f"调试失败: {e}")

if __name__ == "__main__":
    asyncio.run(debug_contracts())
