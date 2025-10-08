"""
EdgeX高频做市策略 v3.7 快速启动脚本

7币种版本 - 方案B配置
- 刷新间隔: 120秒
- API间隔: 1.08秒
- 峰值频率: 0.926次/秒（安全）

使用方法: python run_v3.7.py
"""

import asyncio
import signal
import sys
from loguru import logger

from config import get_my_config
from strategy_hft_v3_7 import HighFrequencyMarketMakingStrategy

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/hft_v3.7_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG"
)

shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    logger.info("收到停止信号...")

async def main():
    global shutdown_requested
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        config = get_my_config()
        
        logger.info("="*70)
        logger.info("🚀 EdgeX高频做市策略 v3.7 - 7币种优化版")
        logger.info("="*70)
        logger.info(f"账户: {config.account_id}")
        logger.info(f"币种: {len(config.symbols)}个 - {', '.join(config.symbols)}")
        logger.info("")
        logger.info("配置参数（方案B）:")
        logger.info("  • 网格间距: 0.045%")
        logger.info("  • 网格层数: 3层")
        logger.info("  • 刷新间隔: 120秒")
        logger.info("  • API间隔: 1.08秒（峰值0.926次/秒）")
        logger.info("")
        logger.info("预期性能:")
        logger.info("  💰 日收益: ~580 USDT")
        logger.info("  📊 日交易量: ~160万美金")
        logger.info("  🚀 年化收益: ~1060%")
        logger.info("="*70)
        logger.info("")
        
        # 使用EMA模式
        strategy = HighFrequencyMarketMakingStrategy(config, optimization_mode="ema")
        
        logger.info("策略启动中... 按 Ctrl+C 停止")
        logger.info("")
        
        strategy_task = asyncio.create_task(strategy.run())
        
        while not shutdown_requested and strategy.is_running:
            await asyncio.sleep(1)
        
        if shutdown_requested:
            logger.info("正在停止策略...")
            strategy.stop()
            try:
                await asyncio.wait_for(strategy_task, timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning("停止超时，强制终止")
                strategy_task.cancel()
        else:
            await strategy_task
        
        # 最终统计
        logger.info("\n" + "="*70)
        logger.info("策略运行结束")
        stats = strategy.get_performance_stats()
        logger.info(f"余额: {stats['balance']:.2f} USDT ({stats['balance_change_pct']:+.2f}%)")
        logger.info(f"交易量: {stats['daily_volume']:.0f} USDT")
        logger.info(f"交易次数: {stats['total_trades']}")
        logger.info(f"净损益: {stats.get('net_pnl', 0):+.2f} USDT")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序退出")

