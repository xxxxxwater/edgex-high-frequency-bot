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
        import edgex_python_sdk
        import aiohttp
        import websockets
        import numpy
        import pandas
        logger.info("所有依赖已安装")
        return True
    except ImportError as e:
        logger.error(f"缺少依赖: {e}")
        logger.error("请运行: pip install -r requirements.txt")
        return False

def check_config():
    """检查配置"""
    try:
        from config import load_config
        config = load_config()
        
        if not config.api_key or config.api_key == "your_api_key_here":
            logger.error("请先配置API密钥")
            logger.error("1. 复制 config_local.py.template 为 config_local.py")
            logger.error("2. 编辑 config_local.py 填入您的API密钥")
            return False
        
        logger.info("配置检查通过")
        return True
    except Exception as e:
        logger.error(f"配置检查失败: {e}")
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
    print("\n是否运行配置测试？(y/n): ", end="")
    choice = input().lower().strip()
    
    if choice == 'y':
        logger.info("运行配置测试...")
        from test_config import test_config
        if not await test_config():
            logger.error("配置测试失败，请检查配置")
            sys.exit(1)
        logger.info("配置测试通过！")
    
    # 询问是否启动交易机器人
    print("\n是否启动交易机器人？(y/n): ", end="")
    choice = input().lower().strip()
    
    if choice == 'y':
        logger.info("启动交易机器人...")
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
