"""
EdgeX高频交易机器人主程序
"""

import asyncio
import signal
import sys
import os
from loguru import logger
from config import load_config, validate_config
from strategy import HighFrequencyStrategy
from monitor import PerformanceMonitor
import edgex_types  # 确保模块被导入

class TradingBot:
    """交易机器人主类"""
    
    def __init__(self):
        self.config = load_config()
        self.strategy = None
        self.monitor = None
        self.is_running = False
        
        # 设置日志
        self._setup_logging()
        
        # 设置信号处理
        self._setup_signal_handlers()
    
    def _setup_logging(self):
        """设置日志"""
        logger.remove()  # 移除默认处理器
        
        # 添加控制台输出
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        # 添加文件输出
        logger.add(
            "logs/trading_bot_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="1 day",
            retention="30 days"
        )
        
        logger.info("日志系统初始化完成")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备停止...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self):
        """初始化机器人"""
        try:
            logger.info("初始化交易机器人...")
            
            # 验证配置
            if not validate_config(self.config):
                logger.error("配置验证失败，请检查配置文件")
                return False
            
            if not self.config.stark_private_key or not self.config.account_id:
                logger.error("Stark私钥或账户ID未配置，请检查.env文件")
                logger.error("必填项：EDGEX_STARK_PRIVATE_KEY 和 EDGEX_ACCOUNT_ID")
                return False
            
            # 创建策略实例
            self.strategy = HighFrequencyStrategy(self.config)
            logger.info("策略初始化完成")
            
            # 创建性能监控器
            self.monitor = PerformanceMonitor(self.strategy)
            logger.info("性能监控器初始化完成")
            
            # 创建价格流（可选，用于WebSocket实时数据）
            # if self.config.testnet:
            #     self.price_stream = RealTimePriceStream(self.config)
            #     logger.info("价格流初始化完成")
            
            logger.info("交易机器人初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def start(self):
        """启动机器人"""
        if self.is_running:
            logger.warning("机器人已在运行")
            return
        
        try:
            logger.info("启动交易机器人...")
            self.is_running = True
            
            # 启动性能监控
            await self.monitor.start_monitoring()
            
            # 启动策略
            strategy_task = asyncio.create_task(self.strategy.run())
            
            # 等待任务完成
            await asyncio.gather(strategy_task, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """停止机器人"""
        if not self.is_running:
            return
        
        logger.info("停止交易机器人...")
        self.is_running = False
        
        try:
            # 停止策略
            if self.strategy:
                self.strategy.stop()
            
            # 停止监控
            if self.monitor:
                await self.monitor.stop_monitoring()
            
            logger.info("交易机器人已停止")
            
        except Exception as e:
            logger.error(f"停止过程中发生错误: {e}")
    
    async def run(self):
        """运行机器人"""
        if not await self.initialize():
            logger.error("初始化失败，退出程序")
            return
        
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号")
        except Exception as e:
            logger.error(f"运行过程中发生错误: {e}")
        finally:
            await self.stop()

async def main():
    """主函数"""
    # 创建必要的目录
    import os
    os.makedirs("logs", exist_ok=True)
    
    # 创建并运行机器人
    bot = TradingBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)
