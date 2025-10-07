#!/usr/bin/env python3
"""
配置文件管理器
支持从环境变量、配置文件或交互式输入获取配置
"""

import os
import sys
from typing import Dict, Optional
from pathlib import Path


def get_config_from_env() -> Dict[str, str]:
    """从环境变量获取配置"""
    config = {
        # 账户配置
        'EDGEX_ACCOUNT_ID': os.getenv('EDGEX_ACCOUNT_ID', ''),
        'EDGEX_STARK_PRIVATE_KEY': os.getenv('EDGEX_STARK_PRIVATE_KEY', ''),
        'EDGEX_PUBLIC_KEY': os.getenv('EDGEX_PUBLIC_KEY', ''),
        'EDGEX_PUBLIC_KEY_Y_COORDINATE': os.getenv('EDGEX_PUBLIC_KEY_Y_COORDINATE', ''),
        'EDGEX_API_KEY': os.getenv('EDGEX_API_KEY', ''),
        'EDGEX_SECRET_KEY': os.getenv('EDGEX_SECRET_KEY', ''),
        
        # 网络配置
        'EDGEX_TESTNET': os.getenv('EDGEX_TESTNET', 'false'),
        
        # 交易配置
        'EDGEX_SYMBOLS': os.getenv('EDGEX_SYMBOLS', 'BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT'),
        
        # 策略参数
        'EDGEX_BASE_POSITION_SIZE': os.getenv('EDGEX_BASE_POSITION_SIZE', '0.05'),
        'EDGEX_LEVERAGE': os.getenv('EDGEX_LEVERAGE', '50'),
        'EDGEX_TAKE_PROFIT_PCT': os.getenv('EDGEX_TAKE_PROFIT_PCT', '0.004'),
        'EDGEX_STOP_LOSS_PCT': os.getenv('EDGEX_STOP_LOSS_PCT', '0.004'),
        'EDGEX_TARGET_VOLATILITY': os.getenv('EDGEX_TARGET_VOLATILITY', '0.60'),
        
        # 风控配置
        'EDGEX_MIN_ORDER_SIZE': os.getenv('EDGEX_MIN_ORDER_SIZE', '0.3'),
        'EDGEX_MAX_POSITION_PCT': os.getenv('EDGEX_MAX_POSITION_PCT', '0.5'),
        
        # 交易频率
        'EDGEX_MIN_TRADE_INTERVAL': os.getenv('EDGEX_MIN_TRADE_INTERVAL', '5000'),
        'EDGEX_MAX_TRADE_INTERVAL': os.getenv('EDGEX_MAX_TRADE_INTERVAL', '60000'),
        
        # 监控配置
        'EDGEX_PERFORMANCE_REPORT_INTERVAL': os.getenv('EDGEX_PERFORMANCE_REPORT_INTERVAL', '300'),
        'EDGEX_LOG_LEVEL': os.getenv('EDGEX_LOG_LEVEL', 'INFO'),
    }
    return config


def load_config_file(file_path: str) -> Dict[str, str]:
    """从配置文件加载配置"""
    config = {}
    if not os.path.exists(file_path):
        return config
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    
    return config


def save_config_file(config: Dict[str, str], file_path: str):
    """保存配置到文件"""
    template = """# ============================================================
# EdgeX 交易机器人配置
# ============================================================

# ============================================================
# EdgeX 账户配置
# ============================================================
EDGEX_ACCOUNT_ID={EDGEX_ACCOUNT_ID}
EDGEX_STARK_PRIVATE_KEY={EDGEX_STARK_PRIVATE_KEY}
EDGEX_PUBLIC_KEY={EDGEX_PUBLIC_KEY}
EDGEX_PUBLIC_KEY_Y_COORDINATE={EDGEX_PUBLIC_KEY_Y_COORDINATE}

# API密钥（EdgeX SDK使用Stark签名，可留空）
EDGEX_API_KEY={EDGEX_API_KEY}
EDGEX_SECRET_KEY={EDGEX_SECRET_KEY}

# ============================================================
# 网络配置
# ============================================================
EDGEX_TESTNET={EDGEX_TESTNET}

# ============================================================
# 交易配置
# ============================================================
EDGEX_SYMBOLS={EDGEX_SYMBOLS}

# ============================================================
# 策略参数
# ============================================================
EDGEX_BASE_POSITION_SIZE={EDGEX_BASE_POSITION_SIZE}
EDGEX_LEVERAGE={EDGEX_LEVERAGE}
EDGEX_TAKE_PROFIT_PCT={EDGEX_TAKE_PROFIT_PCT}
EDGEX_STOP_LOSS_PCT={EDGEX_STOP_LOSS_PCT}
EDGEX_TARGET_VOLATILITY={EDGEX_TARGET_VOLATILITY}

# ============================================================
# 风控配置
# ============================================================
EDGEX_MIN_ORDER_SIZE={EDGEX_MIN_ORDER_SIZE}
EDGEX_MAX_POSITION_PCT={EDGEX_MAX_POSITION_PCT}

# ============================================================
# 交易频率配置
# ============================================================
EDGEX_MIN_TRADE_INTERVAL={EDGEX_MIN_TRADE_INTERVAL}
EDGEX_MAX_TRADE_INTERVAL={EDGEX_MAX_TRADE_INTERVAL}

# ============================================================
# 监控配置
# ============================================================
EDGEX_PERFORMANCE_REPORT_INTERVAL={EDGEX_PERFORMANCE_REPORT_INTERVAL}
EDGEX_LOG_LEVEL={EDGEX_LOG_LEVEL}
"""
    
    content = template.format(**config)
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ 配置已保存到: {file_path}")


def validate_config(config: Dict[str, str]) -> bool:
    """验证配置的必需字段"""
    required_fields = [
        'EDGEX_ACCOUNT_ID',
        'EDGEX_STARK_PRIVATE_KEY',
        'EDGEX_PUBLIC_KEY',
        'EDGEX_PUBLIC_KEY_Y_COORDINATE'
    ]
    
    missing = []
    for field in required_fields:
        if not config.get(field):
            missing.append(field)
    
    if missing:
        print(f"❌ 缺少必需的配置字段: {', '.join(missing)}")
        return False
    
    return True


def interactive_config() -> Dict[str, str]:
    """交互式配置"""
    print("\n" + "="*60)
    print("EdgeX 交易机器人 - 配置向导")
    print("="*60 + "\n")
    
    config = {}
    
    # 必需字段
    print("📝 请输入账户信息（必填）：\n")
    config['EDGEX_ACCOUNT_ID'] = input("账户ID (EDGEX_ACCOUNT_ID): ").strip()
    config['EDGEX_STARK_PRIVATE_KEY'] = input("Stark私钥 (EDGEX_STARK_PRIVATE_KEY): ").strip()
    config['EDGEX_PUBLIC_KEY'] = input("公钥 (EDGEX_PUBLIC_KEY): ").strip()
    config['EDGEX_PUBLIC_KEY_Y_COORDINATE'] = input("公钥Y坐标 (EDGEX_PUBLIC_KEY_Y_COORDINATE): ").strip()
    
    # 可选字段
    print("\n📝 API密钥（可选，直接回车跳过）：\n")
    config['EDGEX_API_KEY'] = input("API密钥 (EDGEX_API_KEY) [可选]: ").strip()
    config['EDGEX_SECRET_KEY'] = input("Secret密钥 (EDGEX_SECRET_KEY) [可选]: ").strip()
    
    # 网络模式
    print("\n🌐 网络配置：\n")
    testnet = input("使用测试网? (y/n) [默认: n]: ").strip().lower()
    config['EDGEX_TESTNET'] = 'true' if testnet == 'y' else 'false'
    
    # 交易对
    print("\n💰 交易配置：\n")
    symbols = input("交易对 (逗号分隔) [默认: BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT]: ").strip()
    config['EDGEX_SYMBOLS'] = symbols if symbols else 'BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT'
    
    # 策略参数（使用默认值）
    print("\n⚙️  策略参数（使用默认值）：\n")
    config['EDGEX_BASE_POSITION_SIZE'] = '0.05'
    config['EDGEX_LEVERAGE'] = '50'
    config['EDGEX_TAKE_PROFIT_PCT'] = '0.004'
    config['EDGEX_STOP_LOSS_PCT'] = '0.004'
    config['EDGEX_TARGET_VOLATILITY'] = '0.60'
    config['EDGEX_MIN_ORDER_SIZE'] = '0.3'
    config['EDGEX_MAX_POSITION_PCT'] = '0.5'
    config['EDGEX_MIN_TRADE_INTERVAL'] = '5000'
    config['EDGEX_MAX_TRADE_INTERVAL'] = '60000'
    config['EDGEX_PERFORMANCE_REPORT_INTERVAL'] = '300'
    config['EDGEX_LOG_LEVEL'] = 'INFO'
    
    return config


def main():
    """主函数"""
    # 检查是否有配置文件路径参数
    config_file = sys.argv[1] if len(sys.argv) > 1 else '.env'
    
    # 尝试从环境变量加载
    config = get_config_from_env()
    
    # 如果环境变量中没有必需字段，尝试从文件加载
    if not validate_config(config):
        print(f"\n📂 尝试从文件加载配置: {config_file}")
        file_config = load_config_file(config_file)
        
        if file_config:
            config.update(file_config)
        
        # 如果仍然没有必需字段，进入交互式配置
        if not validate_config(config):
            print("\n❌ 未找到有效配置，启动交互式配置向导...\n")
            config = interactive_config()
            
            # 验证配置
            if not validate_config(config):
                print("\n❌ 配置无效，退出")
                sys.exit(1)
            
            # 保存配置
            save_choice = input(f"\n💾 是否保存配置到 {config_file}? (y/n): ").strip().lower()
            if save_choice == 'y':
                save_config_file(config, config_file)
    else:
        print("✅ 从环境变量加载配置成功")
    
    print("\n" + "="*60)
    print("配置验证通过！")
    print("="*60)
    print(f"账户ID: {config['EDGEX_ACCOUNT_ID']}")
    print(f"网络模式: {'测试网' if config['EDGEX_TESTNET'] == 'true' else '主网'}")
    print(f"交易对: {config['EDGEX_SYMBOLS']}")
    print(f"杠杆: {config['EDGEX_LEVERAGE']}x")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

