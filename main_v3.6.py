"""
EdgeX高频做市网格策略 - 主程序 v3.6

使用config.py中的账户信息运行高频做市策略
支持三种优化模式：
1. baseline - 基准模式（v3.5原始配置）
2. ema - EMA优化模式（增加趋势交易对冲手续费）
3. wider_grid - 更宽网格模式（降低交易频率）

@version 3.6
@date 2025-10-08
"""

import asyncio
import signal
import sys
from loguru import logger

from config import get_my_config
from strategy_hft_v3_6 import HighFrequencyMarketMakingStrategy


# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/hft_strategy_v3.6_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG"
)


def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，准备停止策略...")
    global shutdown_requested
    shutdown_requested = True


shutdown_requested = False


async def main():
    """主函数"""
    global shutdown_requested
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 加载配置
        logger.info("加载你的配置...")
        config = get_my_config()
        
        logger.info("配置已加载:")
        logger.info(f"  账户ID: {config.account_id}")
        logger.info(f"  环境: {'测试网' if config.testnet else '生产网'}")
        logger.info(f"  交易对: {', '.join(config.symbols)}")
        
        # 选择优化模式
        print("\n" + "="*60)
        print("请选择优化模式:")
        print("="*60)
        print("1. baseline    - 基准模式 (v3.5配置, 网格0.05%)")
        print("2. ema         - EMA优化 (网格0.05% + EMA趋势交易) 【推荐】")
        print("3. wider_grid  - 更宽网格 (网格0.08%, 降低交易频率)")
        print("="*60)
        
        # 默认使用EMA模式（根据分析这是最优方案）
        optimization_mode = "ema"
        
        mode_input = input("请输入模式编号 (1/2/3) [默认: 2-ema]: ").strip()
        
        if mode_input == "1":
            optimization_mode = "baseline"
        elif mode_input == "3":
            optimization_mode = "wider_grid"
        elif mode_input == "" or mode_input == "2":
            optimization_mode = "ema"
        else:
            logger.warning(f"无效输入 '{mode_input}'，使用默认模式: ema")
            optimization_mode = "ema"
        
        logger.info(f"已选择模式: {optimization_mode}")
        
        # 确认运行
        logger.warning("")
        logger.warning("⚠️  重要提示：")
        logger.warning("  - 这将使用真实资金进行交易")
        logger.warning("  - 请确保已充分测试策略")
        logger.warning("  - 建议先用小额资金测试")
        logger.warning("")
        
        confirm = input("确认继续运行? (yes/no): ").strip().lower()
        if confirm not in ["yes", "y", "是"]:
            logger.info("用户取消运行")
            return
        
        # 创建策略
        logger.info(f"初始化策略 ({optimization_mode}模式)...")
        strategy = HighFrequencyMarketMakingStrategy(config, optimization_mode=optimization_mode)
        
        # 运行策略
        logger.info("启动策略...")
        strategy_task = asyncio.create_task(strategy.run())
        
        # 等待策略运行或收到停止信号
        while not shutdown_requested and strategy.is_running:
            await asyncio.sleep(1)
        
        if shutdown_requested:
            logger.info("收到停止请求，正在停止策略...")
            strategy.stop()
            
            # 等待策略任务完成（最多60秒）
            try:
                await asyncio.wait_for(strategy_task, timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning("策略停止超时，强制终止")
                strategy_task.cancel()
        else:
            # 策略自行停止
            await strategy_task
        
        # 输出最终统计
        logger.info("\n" + "="*60)
        logger.info("策略运行结束")
        stats = strategy.get_performance_stats()
        logger.info(f"优化模式: {stats['optimization_mode']}")
        logger.info(f"最终余额: {stats['balance']:.2f} USDT")
        logger.info(f"盈亏: {stats['balance_change_pct']:+.2f}%")
        logger.info(f"今日交易量: {stats['daily_volume']:.2f} USDT ({stats['volume_multiple']:.1f}x净值)")
        logger.info(f"总交易次数: {stats['total_trades']}")
        logger.info(f"估算手续费: {stats['estimated_commission']:.2f} USDT")
        
        if optimization_mode == "ema":
            logger.info(f"EMA信号交易: {stats['ema_trades']}次")
            logger.info(f"EMA信号利润: {stats['ema_profit']:+.2f} USDT")
        
        logger.info(f"净损益: {stats['net_pnl']:+.2f} USDT")
        logger.info("="*60)
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"程序运行错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    # 运行主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    except Exception as e:
        logger.error(f"未捕获的异常: {e}")
        sys.exit(1)

