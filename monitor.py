"""
性能监控模块
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from loguru import logger

from edgex_types import PerformanceReport
from strategy import HighFrequencyStrategy

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, strategy: HighFrequencyStrategy):
        self.strategy = strategy
        self.is_monitoring = False
        self.monitor_task = None
    
    async def start_monitoring(self):
        """启动监控"""
        if self.is_monitoring:
            logger.warning("监控已在运行")
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("性能监控已启动")
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("性能监控已停止")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                report = await self._generate_performance_report()
                self._print_report(report)
                
                # 等待下次报告
                await asyncio.sleep(self.strategy.config.performance_report_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟
    
    async def _generate_performance_report(self) -> PerformanceReport:
        """生成性能报告"""
        stats = self.strategy.get_performance_stats()
        
        # 计算交易量
        daily_volume = float(self.strategy._calculate_daily_volume())
        volume_target = float(self.strategy.balance) * 100.0
        volume_ratio = daily_volume / volume_target if volume_target > 0 else 0
        
        # 计算今日盈亏
        today_pnl = 0.0
        now = datetime.now()
        for record in self.strategy.trade_records:
            trade_time = datetime.fromtimestamp(record.timestamp)
            if (now - trade_time).total_seconds() < 86400:  # 24小时内
                today_pnl += float(record.pnl)
        
        return PerformanceReport(
            timestamp=datetime.now(),
            portfolio_value=float(stats["balance"]),
            current_volatility=0.0,  # 波动率已移除
            target_volatility=0.0,    # 波动率已移除
            volatility_ratio=0.0,     # 波动率已移除
            daily_volume=daily_volume,
            volume_target=volume_target,
            volume_ratio=volume_ratio,
            today_trades=stats["total_trades"],
            today_pnl=today_pnl,
            trading_interval=stats["trading_interval"]
        )
    
    def _print_report(self, report: PerformanceReport):
        """打印报告"""
        print("\n" + "="*70)
        print("多币种高频策略性能报告 (v3.4 - WebSocket版)")
        print("="*70)
        print(f"时间: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"净值: {report.portfolio_value:.2f} USDT")
        print(f"今日盈亏: {report.today_pnl:.4f} USDT")
        print(f"交易量: {report.daily_volume:.2f} / {report.volume_target:.2f} ({report.volume_ratio*100:.2f}%)")
        print(f"交易次数: {report.today_trades}")
        print(f"交易间隔: {report.trading_interval}秒")
        
        # 添加详细统计
        stats = self.strategy.get_performance_stats()
        print(f"胜率: {stats['win_rate']*100:.2f}%")
        print(f"盈利交易: {stats['winning_trades']}")
        print(f"亏损交易: {stats['losing_trades']}")
        print(f"活跃仓位: {stats['active_positions']}")
        
        # 显示各交易对持仓
        if stats['active_positions'] > 0:
            print(f"\n持仓详情:")
            for symbol, position in self.strategy.positions.items():
                print(f"  {symbol}: {position.direction.value} | "
                      f"数量: {float(position.size):.6f} | "
                      f"入场: {float(position.entry_price):.2f}")
        
        print("="*70)
    
    async def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        stats = self.strategy.get_performance_stats()
        
        # 计算更多统计信息
        total_pnl = sum(float(record.pnl) for record in self.strategy.trade_records)
        avg_trade_pnl = total_pnl / len(self.strategy.trade_records) if self.strategy.trade_records else 0
        
        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown()
        
        # 计算夏普比率（简化版）
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        return {
            **stats,
            "total_pnl": total_pnl,
            "avg_trade_pnl": avg_trade_pnl,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_trade_records": len(self.strategy.trade_records)
        }
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if len(self.strategy.equity_history) < 2:
            return 0.0
        
        peak = self.strategy.equity_history[0]
        max_dd = 0.0
        
        for value in self.strategy.equity_history:
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / peak
                max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def _calculate_sharpe_ratio(self) -> float:
        """计算夏普比率（简化版）"""
        if len(self.strategy.equity_history) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(self.strategy.equity_history)):
            ret = (self.strategy.equity_history[i] - self.strategy.equity_history[i-1]) / self.strategy.equity_history[i-1]
            returns.append(ret)
        
        if len(returns) < 2:
            return 0.0
        
        import numpy as np
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # 假设无风险利率为0
        return mean_return / std_return * np.sqrt(252)  # 年化
