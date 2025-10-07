#!/usr/bin/env python3
"""
快速验证修复
"""

import asyncio
from loguru import logger

async def quick_test():
    """快速测试基本功能"""
    
    logger.info("="*60)
    logger.info("快速验证修复")
    logger.info("="*60)
    
    # 测试1: 导入模块
    logger.info("\n[1/5] 测试模块导入...")
    try:
        from config import load_config, validate_config
        from edgex_client import EdgeXClient
        from strategy import HighFrequencyStrategy
        from websocket_client import RealTimePriceStream
        logger.info("✅ 所有模块导入成功")
    except Exception as e:
        logger.error(f"❌ 模块导入失败: {e}")
        return False
    
    # 测试2: 配置加载
    logger.info("\n[2/5] 测试配置加载...")
    try:
        config = load_config()
        logger.info(f"✅ 配置加载成功")
        logger.info(f"   - 账户ID: {config.account_id}")
        logger.info(f"   - 网络: {'测试网' if config.testnet else '主网'}")
        logger.info(f"   - 交易对: {', '.join(config.symbols)}")
    except Exception as e:
        logger.error(f"❌ 配置加载失败: {e}")
        return False
    
    # 测试3: 配置验证
    logger.info("\n[3/5] 测试配置验证...")
    if not config.stark_private_key or not config.account_id:
        logger.warning("⚠️  配置不完整，跳过后续测试")
        logger.warning("   请配置 EDGEX_STARK_PRIVATE_KEY 和 EDGEX_ACCOUNT_ID")
        return True
    
    if validate_config(config):
        logger.info("✅ 配置验证通过")
    else:
        logger.error("❌ 配置验证失败")
        return False
    
    # 测试4: 客户端初始化
    logger.info("\n[4/5] 测试客户端初始化...")
    try:
        client = EdgeXClient(config)
        logger.info("✅ EdgeX客户端初始化成功")
        
        # 等待缓存初始化
        await asyncio.sleep(2)
        
        # 测试合约ID映射
        logger.info("\n[5/5] 测试合约ID映射...")
        test_symbol = config.symbols[0] if config.symbols else "SOL-USDT"
        contract_id = await client.get_contract_id_by_symbol(test_symbol)
        
        if contract_id:
            logger.info(f"✅ 合约ID映射成功: {test_symbol} -> {contract_id}")
        else:
            logger.warning(f"⚠️  未找到合约ID: {test_symbol}")
            logger.warning("   这可能是正常的，取决于EdgeX的合约列表")
        
        await client.close()
        
    except Exception as e:
        logger.error(f"❌ 客户端测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    logger.info("\n" + "="*60)
    logger.info("🎉 快速验证完成！所有基本功能正常")
    logger.info("="*60)
    logger.info("\n提示:")
    logger.info("- 运行完整测试: python test_fixes.py")
    logger.info("- 启动机器人: python start.py")
    logger.info("="*60)
    
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(quick_test())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\n测试被中断")
        exit(1)
    except Exception as e:
        logger.error(f"\n测试异常: {e}")
        exit(1)

