#!/usr/bin/env python3
"""
测试K线数据获取
"""

import asyncio
from loguru import logger
from config import load_config
from config import validate_config
from sdk.edgex_sdk import Client as EdgeXSDKClient
from sdk.edgex_sdk.quote.client import GetKLineParams

async def test_klines():
    """测试K线数据获取"""
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
        
        # 获取元数据
        logger.info("获取元数据...")
        metadata = await sdk_client.get_metadata()
        logger.info(f"元数据获取成功: {metadata.get('code')}")
        
        # 查找合约ID
        contracts = metadata.get("data", {}).get("contractList", [])
        logger.info(f"找到 {len(contracts)} 个合约")
        
        # 查找我们需要的合约
        target_contracts = {
            "BTC-USDT": "BTCUSD",
            "ETH-USDT": "ETHUSD", 
            "SOL-USDT": "SOLUSD",
            "BNB-USDT": "BNB2USD"
        }
        
        contract_ids = {}
        for symbol, edgex_symbol in target_contracts.items():
            for contract in contracts:
                if contract.get("contractName") == edgex_symbol:
                    contract_id = contract.get("contractId")
                    contract_ids[symbol] = contract_id
                    logger.info(f"{symbol} ({edgex_symbol}) -> {contract_id}")
                    break
        
        # 测试获取K线数据
        for symbol, contract_id in contract_ids.items():
            logger.info(f"\n测试 {symbol} (合约ID: {contract_id}) 的K线数据...")
            
            # 创建K线参数
            params = GetKLineParams(
                contract_id=contract_id,
                interval="1m",
                size="10"  # 只获取10根K线
            )
            
            # 获取K线数据
            kline_response = await sdk_client.quote.get_k_line(params)
            logger.info(f"K线响应: {kline_response.get('code')}")
            logger.info(f"完整响应: {kline_response}")
            
            if kline_response.get("code") == "SUCCESS":
                kline_data = kline_response.get("data", {}).get("kLineList", [])
                logger.info(f"获取到 {len(kline_data)} 根K线")
                
                if kline_data:
                    # 显示第一根和最后一根K线
                    first_kline = kline_data[0]
                    last_kline = kline_data[-1]
                    logger.info(f"第一根K线: {first_kline}")
                    logger.info(f"最后一根K线: {last_kline}")
                else:
                    logger.warning(f"{symbol}: K线数据为空")
                    logger.info(f"数据结构: {kline_response.get('data', {})}")
            else:
                logger.error(f"{symbol}: 获取K线失败 - {kline_response}")
        
        await sdk_client.close()
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_klines())
