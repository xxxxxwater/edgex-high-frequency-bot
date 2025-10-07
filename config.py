"""
配置管理模块
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from loguru import logger


class Config(BaseModel):
    """机器人配置"""
    
    # EdgeX API配置
    api_key: str = Field("", description="EdgeX API Key（可选）")
    secret_key: str = Field("", description="EdgeX Secret Key（可选）")
    stark_private_key: Optional[str] = Field(None, description="Stark私钥（用于交易签名，必填）")
    account_id: Optional[str] = Field(None, description="EdgeX账户ID（必填）")
    
    # Stark公钥信息（可选，用于验证）
    public_key: Optional[str] = Field(None, description="Stark公钥")
    public_key_y_coordinate: Optional[str] = Field(None, description="Stark公钥Y坐标")
    
    # 网络配置
    testnet: bool = Field(False, description="是否使用测试网（False=主网，True=测试网）")
    
    # 交易配置
    symbols: List[str] = Field(
        ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"], 
        description="交易对列表（支持多交易对并发交易）"
    )
    
    # 策略配置
    base_position_size: float = Field(0.05, description="基础仓位比例（5%，固定）")
    leverage: int = Field(50, description="杠杆倍数")
    take_profit_pct: float = Field(0.004, description="止盈百分比（0.4%）")
    stop_loss_pct: float = Field(0.004, description="止损百分比（0.4%）")
    
    # 风控配置
    min_order_size: float = Field(0.3, description="最小下单量（SOL）")
    max_position_pct: float = Field(0.5, description="最大仓位比例（50%）")
    
    # 交易频率配置
    min_trade_interval: int = Field(5000, description="最小交易间隔（毫秒）")
    max_trade_interval: int = Field(60000, description="最大交易间隔（毫秒）")
    
    # 监控配置
    performance_report_interval: int = Field(300, description="性能报告间隔（秒）")
    
    # 日志配置
    log_level: str = Field("INFO", description="日志级别")
    
    class Config:
        env_prefix = "EDGEX_"


def load_config() -> Config:
    """
    从环境变量加载配置
    
    Returns:
        Config: 配置对象
    """
    # 加载.env文件
    load_dotenv()
    
    # 从环境变量读取配置
    config_dict = {
        "api_key": os.getenv("EDGEX_API_KEY", ""),
        "secret_key": os.getenv("EDGEX_SECRET_KEY", ""),
        "stark_private_key": os.getenv("EDGEX_STARK_PRIVATE_KEY"),
        "account_id": os.getenv("EDGEX_ACCOUNT_ID"),
        "public_key": os.getenv("EDGEX_PUBLIC_KEY"),
        "public_key_y_coordinate": os.getenv("EDGEX_PUBLIC_KEY_Y_COORDINATE"),
        "testnet": os.getenv("EDGEX_TESTNET", "false").lower() == "true",
        "symbols": os.getenv("EDGEX_SYMBOLS", "SOL-USDT").split(","),
        "base_position_size": float(os.getenv("EDGEX_BASE_POSITION_SIZE", "0.05")),
        "leverage": int(os.getenv("EDGEX_LEVERAGE", "50")),
        "take_profit_pct": float(os.getenv("EDGEX_TAKE_PROFIT_PCT", "0.004")),
        "stop_loss_pct": float(os.getenv("EDGEX_STOP_LOSS_PCT", "0.004")),
        "min_order_size": float(os.getenv("EDGEX_MIN_ORDER_SIZE", "0.3")),
        "max_position_pct": float(os.getenv("EDGEX_MAX_POSITION_PCT", "0.5")),
        "min_trade_interval": int(os.getenv("EDGEX_MIN_TRADE_INTERVAL", "5000")),
        "max_trade_interval": int(os.getenv("EDGEX_MAX_TRADE_INTERVAL", "60000")),
        "performance_report_interval": int(os.getenv("EDGEX_PERFORMANCE_REPORT_INTERVAL", "300")),
        "log_level": os.getenv("EDGEX_LOG_LEVEL", "INFO"),
    }
    
    try:
        config = Config(**config_dict)
        logger.info("配置加载成功")
        logger.info(f"网络模式: {'测试网' if config.testnet else '主网 ⚠️'}")
        logger.info(f"账户ID: {config.account_id}")
        logger.info(f"交易对: {config.symbols}")
        logger.info(f"杠杆倍数: {config.leverage}x")
        logger.info(f"基础仓位: {config.base_position_size * 100}%")
        return config
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        raise


def validate_config(config: Config) -> bool:
    """
    验证配置
    
    Args:
        config: 配置对象
        
    Returns:
        bool: 验证是否通过
    """
    errors = []
    
    # 验证Stark签名配置（EdgeX使用Stark签名，不需要API Key）
    if not config.stark_private_key:
        errors.append("Stark私钥未配置（EDGEX_STARK_PRIVATE_KEY）")
    
    if not config.account_id:
        errors.append("账户ID未配置（EDGEX_ACCOUNT_ID）")
    
    # 验证交易参数
    if config.base_position_size <= 0 or config.base_position_size > 1:
        errors.append("基础仓位比例必须在0-1之间")
    
    if config.leverage < 1 or config.leverage > 100:
        errors.append("杠杆倍数必须在1-100之间")
    
    if config.take_profit_pct <= 0:
        errors.append("止盈百分比必须大于0")
    
    if config.stop_loss_pct <= 0:
        errors.append("止损百分比必须大于0")
    
    
    if config.min_order_size <= 0:
        errors.append("最小下单量必须大于0")
    
    if errors:
        for error in errors:
            logger.error(f"配置验证失败: {error}")
        return False
    
    logger.info("配置验证通过")
    return True


# 创建全局配置实例
def get_config() -> Config:
    """获取全局配置实例"""
    return load_config()

