#!/usr/bin/env python3
"""
测试不同的K线参数
"""

import asyncio
from loguru import logger
from config import load_config
from config import validate_config
from sdk.edgex_sdk import Client as EdgeXSDKClient
from sdk.edgex_sdk.quote.client import GetKLineParams

async def test_different_kline_params():
    """测试不同的K线参数"""
    try:
        # 加载配置
        config = load_config()
        validate_config(config)
        
        # 确定base_url
        if config.testnet:
            base_url = "https://testnet.edgex.exchange"
        else:
            base_url = "https://pro.edgex.exchange"
        
        # 创建SDK客户端
        sdk_client = EdgeXSDKClient(
            base_url=base_url,
            account_id=int(config.account_id) if config.account_id else 0,
            stark_private_key=config.stark_private_key or ""
        )
        
        # 测试BTC-USDT (合约ID: 10000001)
        contract_id = "10000001"
        symbol = "BTC-USDT"
        
        # 测试不同的参数组合
        test_cases = [
            {"interval": "1m", "size": "5", "description": "1分钟K线，5根"},
            {"interval": "5m", "size": "5", "description": "5分钟K线，5根"},
            {"interval": "1h", "size": "5", "description": "1小时K线，5根"},
            {"interval": "1m", "size": "1", "description": "1分钟K线，1根"},
            {"interval": "1m", "size": "100", "description": "1分钟K线，100根"},
        ]
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"\n=== 测试 {i+1}: {test_case['description']} ===")
            
            try:
                # 创建K线参数
                params = GetKLineParams(
                    contract_id=contract_id,
                    interval=test_case["interval"],
                    size=test_case["size"]
                )
                
                # 获取K线数据
                kline_response = await sdk_client.quote.get_k_line(params)
                logger.info(f"响应码: {kline_response.get('code')}")
                
                if kline_response.get("code") == "SUCCESS":
                    kline_data = kline_response.get("data", {}).get("dataList", [])
                    logger.info(f"获取到 {len(kline_data)} 根K线")
                    
                    if kline_data:
                        # 显示第一根K线
                        first_kline = kline_data[0]
                        logger.info(f"第一根K线: {first_kline}")
                        break  # 找到数据就停止
                    else:
                        logger.warning("K线数据为空")
                else:
                    logger.error(f"获取K线失败: {kline_response}")
                    
            except Exception as e:
                logger.error(f"测试失败: {e}")
                # 如果是429错误，等待一下再继续
                if "429" in str(e):
                    logger.info("遇到429错误，等待5秒...")
                    await asyncio.sleep(5)
        
        # 测试ticker数据作为替代
        logger.info(f"\n=== 测试 {symbol} 的ticker数据 ===")
        try:
            ticker_response = await sdk_client.quote.get_24_hour_quote(contract_id)
            logger.info(f"Ticker响应: {ticker_response.get('code')}")
            
            if ticker_response.get("code") == "SUCCESS":
                ticker_data = ticker_response.get("data", [])
                logger.info(f"Ticker数据: {ticker_data}")
            else:
                logger.error(f"获取ticker失败: {ticker_response}")
        except Exception as e:
            logger.error(f"Ticker测试失败: {e}")
        
        await sdk_client.close()
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_different_kline_params())
