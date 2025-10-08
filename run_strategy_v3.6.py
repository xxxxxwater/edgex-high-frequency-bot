"""
EdgeX高频做市网格策略 - 非交互式启动器 v3.6

直接运行指定模式的策略，用于演示和测试

使用方法:
    python run_strategy_v3.6.py baseline    # 基准模式
    python run_strategy_v3.6.py ema         # EMA优化模式（默认）
    python run_strategy_v3.6.py wider_grid  # 更宽网格模式

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


shutdown_requested = False


def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，准备停止策略...")
    global shutdown_requested
    shutdown_requested = True


async def main():
    """主函数"""
    global shutdown_requested
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 从命令行参数获取模式
        if len(sys.argv) > 1:
            optimization_mode = sys.argv[1].lower()
        else:
            optimization_mode = "ema"  # 默认使用EMA模式
        
        # 验证模式
        valid_modes = ["baseline", "ema", "wider_grid"]
        if optimization_mode not in valid_modes:
            logger.error(f"无效的模式: {optimization_mode}")
            logger.info(f"有效模式: {', '.join(valid_modes)}")
            sys.exit(1)
        
        # 加载配置
        logger.info("="*60)
        logger.info("EdgeX高频做市策略 v3.6")
        logger.info("="*60)
        logger.info(f"运行模式: {optimization_mode}")
        logger.info("")
        
        config = get_my_config()
        
        logger.info("配置信息:")
        logger.info(f"  账户ID: {config.account_id}")
        logger.info(f"  环境: {'测试网' if config.testnet else '生产网'}")
        logger.info(f"  交易对: {', '.join(config.symbols)}")
        logger.info("")
        
        # 显示模式说明
        mode_descriptions = {
            "baseline": "基准模式 - 网格0.05%, 无EMA",
            "ema": "EMA优化模式 - 网格0.05% + EMA趋势交易（推荐）",
            "wider_grid": "更宽网格模式 - 网格0.08%, 降低交易频率"
        }
        
        logger.info(f"📊 {mode_descriptions[optimization_mode]}")
        logger.info("")
        
        # 显示风险提示
        logger.warning("⚠️  重要提示：")
        logger.warning("  - 这是演示运行，将连接到真实API")
        logger.warning("  - 实际交易请确保充分测试")
        logger.warning("  - 建议先用小额资金测试")
        logger.warning("")
        
        # 创建策略
        logger.info("初始化策略...")
        strategy = HighFrequencyMarketMakingStrategy(config, optimization_mode=optimization_mode)
        
        # 显示预期效果
        if optimization_mode == "ema":
            logger.info("📈 EMA模式预期效果:")
            logger.info("  - 保持100%交易量")
            logger.info("  - 预期对冲约1%手续费")
            logger.info("  - EMA仓位: 25%净值")
            logger.info("  - 止盈/止损: +0.6% / -0.3%")
        elif optimization_mode == "wider_grid":
            logger.info("📈 更宽网格预期效果:")
            logger.info("  - 交易量降低约45%")
            logger.info("  - 手续费降低约63%")
            logger.info("  - 损耗改善约81%")
        else:
            logger.info("📈 基准模式:")
            logger.info("  - v3.5原始配置")
            logger.info("  - 作为对比基准")
        
        logger.info("")
        logger.info("="*60)
        logger.info("策略启动中...")
        logger.info("按 Ctrl+C 停止策略")
        logger.info("="*60)
        logger.info("")
        
        # 运行策略
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
        logger.info("="*60)
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
    # 显示使用说明
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print("\n" + "="*60)
        print("EdgeX高频做市策略 v3.6 - 使用说明")
        print("="*60)
        print("\n使用方法:")
        print("  python run_strategy_v3.6.py [模式]\n")
        print("可用模式:")
        print("  baseline    - 基准模式 (v3.5配置, 网格0.05%)")
        print("  ema         - EMA优化 (网格0.05% + EMA) 【默认推荐】")
        print("  wider_grid  - 更宽网格 (网格0.08%)\n")
        print("示例:")
        print("  python run_strategy_v3.6.py ema\n")
        print("查看对比分析:")
        print("  python compare_optimized_v3.6.py\n")
        print("="*60)
        sys.exit(0)
    
    # 运行主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    except Exception as e:
        logger.error(f"未捕获的异常: {e}")
        sys.exit(1)

