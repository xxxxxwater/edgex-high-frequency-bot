#!/usr/bin/env python3
"""
测试K线API原始响应
"""

import asyncio
from loguru import logger
from config import load_config
from edgex_client import EdgeXClient
from sdk.edgex_sdk import GetKLineParams

async def test_raw_kline():
    """测试K线API原始响应"""
    logger.info("="*60)
    logger.info("测试K线API原始响应")
    logger.info("="*60)
    
    try:
        config = load_config()
        client = EdgeXClient(config)
        
        # 等待缓存初始化
        await asyncio.sleep(2)
        
        # 获取合约ID
        contract_id = await client.get_contract_id_by_symbol("BTC-USDT")
        logger.info(f"BTC-USDT合约ID: {contract_id}")
        
        # 直接调用SDK获取K线
        params = GetKLineParams(
            contract_id=contract_id,
            interval="1m",
            size="10"
        )
        
        logger.info(f"\n调用参数:")
        logger.info(f"  contract_id: {params.contract_id}")
        logger.info(f"  interval: {params.interval}")
        logger.info(f"  size: {params.size}")
        
        response = await client.sdk_client.quote.get_k_line(params)
        
        logger.info(f"\n原始响应:")
        logger.info(f"  类型: {type(response)}")
        logger.info(f"  内容: {response}")
        
        if response:
            logger.info(f"\n响应字段:")
            for key, value in response.items():
                logger.info(f"  {key}: {type(value)} = {value if key != 'data' else '...'}")
            
            if response.get("code") == "SUCCESS":
                data = response.get("data", {})
                logger.info(f"\ndata字段:")
                for key, value in data.items():
                    logger.info(f"  {key}: {type(value)}")
                    if key == "dataList":
                        logger.info(f"    长度: {len(value) if value else 0}")
                        if value and len(value) > 0:
                            logger.info(f"    第一条: {value[0]}")
        
        await client.close()
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_raw_kline())

