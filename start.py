#!/usr/bin/env python3
"""
快速启动脚本
"""

import os
import sys
import asyncio
from loguru import logger

def check_dependencies():
    """检查依赖"""
    try:
        import pydantic
        import dotenv
        from loguru import logger as test_logger
        logger.info("✅ 核心依赖已安装")
        return True
    except ImportError as e:
        logger.error(f"❌ 缺少依赖: {e}")
        logger.error("请运行: pip install -r requirements.txt")
        return False

def check_config():
    """检查配置"""
    try:
        from config import load_config, validate_config
        config = load_config()
        
        if not config.stark_private_key:
            logger.error("❌ 请先配置Stark私钥 (EDGEX_STARK_PRIVATE_KEY)")
            logger.error("1. 复制 .env.example 为 .env")
            logger.error("2. 编辑 .env 填入您的配置信息")
            return False
        
        if not config.account_id:
            logger.error("❌ 请先配置账户ID (EDGEX_ACCOUNT_ID)")
            return False
        
        if not validate_config(config):
            logger.error("❌ 配置验证失败")
            return False
        
        logger.info("✅ 配置检查通过")
        logger.info(f"   账户ID: {config.account_id}")
        logger.info(f"   网络: {'测试网' if config.testnet else '主网'}")
        logger.info(f"   交易对: {', '.join(config.symbols)}")
        return True
    except Exception as e:
        logger.error(f"❌ 配置检查失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """主函数"""
    logger.info("EdgeX高频交易机器人启动检查...")
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查配置
    if not check_config():
        sys.exit(1)
    
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)
    
    # 询问是否运行测试
    print("\n是否运行系统测试？(推荐) (y/n): ", end="")
    choice = input().lower().strip()
    
    if choice == 'y':
        logger.info("运行系统测试...")
        try:
            # 运行test_fixes.py中的测试
            import subprocess
            result = subprocess.run([sys.executable, "test_fixes.py"], 
                                  capture_output=False, 
                                  text=True)
            if result.returncode != 0:
                logger.warning("⚠️ 部分测试未通过，但可以继续运行")
                print("\n是否继续启动？(y/n): ", end="")
                choice = input().lower().strip()
                if choice != 'y':
                    sys.exit(1)
        except Exception as e:
            logger.warning(f"测试运行失败: {e}")
            print("\n是否继续启动？(y/n): ", end="")
            choice = input().lower().strip()
            if choice != 'y':
                sys.exit(1)
    
    # 询问是否启动交易机器人
    print("\n⚠️  确认启动交易机器人？这将使用真实资金交易！(y/n): ", end="")
    choice = input().lower().strip()
    
    if choice == 'y':
        logger.info("🚀 启动交易机器人...")
        from main import main as run_bot
        await run_bot()
    else:
        logger.info("退出程序")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        sys.exit(1)
