"""
工具函数模块
"""

import asyncio
import sys
import os
from typing import Dict, Optional
from loguru import logger

# 添加SDK路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sdk'))

from edgex_sdk import Client as EdgeXSDKClient


async def get_contract_mappings(testnet: bool = True) -> Dict[str, str]:
    """
    获取所有可用的合约ID映射
    
    Args:
        testnet: 是否使用测试网
        
    Returns:
        Dict[str, str]: {交易对名称: 合约ID} 的映射
    """
    base_url = "https://testnet.edgex.exchange" if testnet else "https://pro.edgex.exchange"
    
    # 创建临时客户端（不需要账户信息来获取元数据）
    client = EdgeXSDKClient(
        base_url=base_url,
        account_id=0,
        stark_private_key="0x0"
    )
    
    try:
        metadata = await client.get_metadata()
        
        if not metadata or metadata.get("code") != "SUCCESS":
            logger.error("获取元数据失败")
            return {}
        
        contracts = metadata.get("data", {}).get("contractList", [])
        
        mapping = {}
        for contract in contracts:
            contract_name = contract.get("contractName", "")
            contract_id = contract.get("contractId", "")
            if contract_name and contract_id:
                mapping[contract_name] = contract_id
        
        return mapping
        
    except Exception as e:
        logger.error(f"获取合约映射失败: {e}")
        return {}
    finally:
        await client.close()


async def print_contract_list(testnet: bool = True):
    """
    打印所有可用的合约列表
    
    Args:
        testnet: 是否使用测试网
    """
    logger.info(f"获取{'测试网' if testnet else '主网'}合约列表...")
    
    mappings = await get_contract_mappings(testnet)
    
    if not mappings:
        logger.error("无法获取合约列表")
        return
    
    print("\n" + "="*60)
    print("EdgeX 可用合约列表")
    print("="*60)
    print(f"{'交易对':<20} {'合约ID':<15}")
    print("-"*60)
    
    for symbol, contract_id in sorted(mappings.items()):
        print(f"{symbol:<20} {contract_id:<15}")
    
    print("="*60)
    print(f"总计: {len(mappings)} 个合约\n")


def get_symbol_from_env(env_symbol: str, contract_mappings: Dict[str, str]) -> str:
    """
    将环境变量中的交易对名称转换为合约ID
    
    Args:
        env_symbol: 环境变量中的交易对（如"SOL-USDT"）
        contract_mappings: 合约映射字典
        
    Returns:
        str: 合约ID（如"10000003"）或原始值
    """
    # 如果已经是数字ID，直接返回
    if env_symbol.isdigit():
        return env_symbol
    
    # 尝试从映射中查找
    if env_symbol in contract_mappings:
        return contract_mappings[env_symbol]
    
    # 尝试标准化格式（添加或移除连字符）
    normalized = env_symbol.replace("-", "").replace("_", "")
    for key, value in contract_mappings.items():
        if key.replace("-", "").replace("_", "") == normalized:
            return value
    
    logger.warning(f"未找到交易对 {env_symbol} 的合约ID，使用原始值")
    return env_symbol


async def verify_account_access(config) -> bool:
    """
    验证账户访问权限
    
    Args:
        config: 配置对象
        
    Returns:
        bool: 验证是否成功
    """
    from edgex_client import EdgeXClient
    
    try:
        client = EdgeXClient(config)
        
        # 尝试获取账户信息
        account_info = await client.get_account_info()
        
        logger.info("="*60)
        logger.info("账户验证成功")
        logger.info(f"账户余额: {account_info.balance:.2f} USDT")
        logger.info(f"可用余额: {account_info.available_balance:.2f} USDT")
        logger.info(f"持仓数量: {len(account_info.positions)}")
        logger.info("="*60)
        
        await client.close()
        return True
        
    except Exception as e:
        logger.error(f"账户验证失败: {e}")
        return False


if __name__ == "__main__":
    # 命令行工具
    import argparse
    
    parser = argparse.ArgumentParser(description="EdgeX工具函数")
    parser.add_argument(
        "--list-contracts",
        action="store_true",
        help="列出所有可用合约"
    )
    parser.add_argument(
        "--testnet",
        action="store_true",
        default=True,
        help="使用测试网（默认）"
    )
    parser.add_argument(
        "--mainnet",
        action="store_true",
        help="使用主网"
    )
    parser.add_argument(
        "--verify-account",
        action="store_true",
        help="验证账户访问权限"
    )
    
    args = parser.parse_args()
    
    # 确定使用哪个网络
    use_testnet = args.testnet and not args.mainnet
    
    if args.list_contracts:
        asyncio.run(print_contract_list(use_testnet))
    elif args.verify_account:
        from config import load_config
        config = load_config()
        asyncio.run(verify_account_access(config))
    else:
        parser.print_help()

