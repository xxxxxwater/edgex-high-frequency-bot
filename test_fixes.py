#!/usr/bin/env python3
"""
测试修复后的功能
"""

import asyncio
import sys
from loguru import logger
from config import load_config, validate_config
from edgex_client import EdgeXClient

async def test_contract_mapping():
    """测试合约ID映射"""
    logger.info("=== 测试合约ID映射 ===")
    
    try:
        config = load_config()
        if not validate_config(config):
            logger.error("配置验证失败")
            return False
        
        client = EdgeXClient(config)
        
        # 等待缓存初始化
        await asyncio.sleep(2)
        
        # 测试交易对映射
        test_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"]
        
        success_count = 0
        for symbol in test_symbols:
            try:
                contract_id = await client.get_contract_id_by_symbol(symbol)
                if contract_id:
                    logger.info(f"✅ {symbol} -> {contract_id}")
                    success_count += 1
                else:
                    logger.error(f"❌ {symbol} -> None")
            except Exception as e:
                logger.error(f"❌ {symbol} 映射失败: {e}")
        
        logger.info(f"\n映射成功率: {success_count}/{len(test_symbols)}")
        
        await client.close()
        return success_count > 0
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_kline_fetch():
    """测试K线数据获取"""
    logger.info("\n=== 测试K线数据获取 ===")
    
    try:
        config = load_config()
        client = EdgeXClient(config)
        
        # 等待缓存初始化
        await asyncio.sleep(2)
        
        # 测试获取K线
        test_symbol = config.symbols[0] if config.symbols else "SOL-USDT"
        
        logger.info(f"获取 {test_symbol} 的K线数据...")
        klines = await client.get_klines(test_symbol, "1m", 10)
        
        if klines and len(klines) > 0:
            logger.info(f"✅ 成功获取 {len(klines)} 根K线")
            logger.info(f"最新价格: {klines[-1].close}")
            await client.close()
            return True
        else:
            logger.error("❌ K线数据为空")
            await client.close()
            return False
            
    except Exception as e:
        logger.error(f"❌ K线获取失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_account_info():
    """测试账户信息获取"""
    logger.info("\n=== 测试账户信息获取 ===")
    
    try:
        config = load_config()
        client = EdgeXClient(config)
        
        account_info = await client.get_account_info()
        
        logger.info(f"✅ 账户余额: {account_info.balance:.2f} USDT")
        logger.info(f"✅ 可用余额: {account_info.available_balance:.2f} USDT")
        logger.info(f"✅ 持仓数量: {len(account_info.positions)}")
        
        await client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 账户信息获取失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """主测试函数"""
    logger.info("开始测试修复后的功能...\n")
    
    results = {}
    
    # 测试1: 合约ID映射
    results["contract_mapping"] = await test_contract_mapping()
    
    # 测试2: K线获取
    results["kline_fetch"] = await test_kline_fetch()
    
    # 测试3: 账户信息
    results["account_info"] = await test_account_info()
    
    # 汇总结果
    logger.info("\n" + "="*70)
    logger.info("测试结果汇总")
    logger.info("="*70)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    logger.info(f"\n总体: {success_count}/{total_count} 通过")
    logger.info("="*70)
    
    if success_count == total_count:
        logger.info("🎉 所有测试通过！策略可以正常运行")
        return 0
    else:
        logger.warning("⚠️ 部分测试失败，请检查配置和网络连接")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试异常: {e}")
        sys.exit(1)

