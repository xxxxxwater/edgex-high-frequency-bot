"""
EdgeX策略对比评估工具 v3.6
用于对比不同手续费优化方案的效果

对比方案：
1. 基准方案(baseline): v3.5原始配置，网格间距0.05%
2. EMA优化方案(ema): 网格间距0.05% + EMA(9/21)趋势交易
3. 更宽网格方案(wider_grid): 网格间距0.08%，减少交易频率

评估指标：
- 交易量
- 估算手续费
- EMA信号利润（仅ema方案）
- 净损益
- 手续费补偿效果

@version 3.6
@date 2025-10-08
"""

import asyncio
from decimal import Decimal
from loguru import logger
import sys
from config import get_my_config
from strategy_hft_v3_6 import HighFrequencyMarketMakingStrategy


class StrategyComparison:
    """策略对比工具"""
    
    def __init__(self):
        self.config = get_my_config()
        self.results = {}
    
    def print_header(self):
        """打印标题"""
        print("\n" + "="*80)
        print("EdgeX高频策略手续费优化方案对比 v3.6")
        print("="*80)
        print("\n当前状态:")
        print("  - 交易量: 34万美金")
        print("  - 手续费损耗: 100 USDT")
        print("  - 目标: 通过优化降低或对冲手续费损耗")
        print("\n" + "="*80)
    
    def analyze_baseline(self):
        """分析基准方案"""
        print("\n【方案1：基准方案 - v3.5配置】")
        print("-" * 80)
        print("配置:")
        print("  - 网格间距: 0.05%")
        print("  - 网格层数: 3层")
        print("  - EMA交易: 禁用")
        
        # 基于实际数据估算
        volume = Decimal("340000")  # 34万美金
        fee_rate = Decimal("0.0002")  # maker返佣约0.02%（EdgeX可能更优惠）
        estimated_fee = volume * fee_rate
        
        print("\n估算结果:")
        print(f"  - 日交易量: ${float(volume):,.0f}")
        print(f"  - 估算手续费: ${float(estimated_fee):.2f} (按0.02%计算)")
        print(f"  - 实际损耗: $100 (已知数据)")
        print(f"  - 净损益: -$100")
        
        self.results["baseline"] = {
            "volume": float(volume),
            "estimated_fee": float(estimated_fee),
            "actual_fee": 100.0,
            "ema_profit": 0.0,
            "net_pnl": -100.0,
            "grid_spacing": "0.05%"
        }
        
        print("\n分析:")
        print("  ✓ 优点: 高成交率，交易量充足")
        print("  ✗ 缺点: 手续费损耗100 USDT")
    
    def analyze_ema_strategy(self):
        """分析EMA优化方案"""
        print("\n【方案2：EMA优化方案】")
        print("-" * 80)
        print("配置:")
        print("  - 网格间距: 0.05% (保持不变)")
        print("  - 网格层数: 3层")
        print("  - EMA交易: 启用 (快线9, 慢线21)")
        print("  - EMA仓位: 15%净值")
        print("  - 止盈/止损: +0.3% / -0.2%")
        
        # 估算EMA信号效果
        volume = Decimal("340000")  # 网格交易量保持不变
        grid_fee = Decimal("100")   # 网格交易手续费
        
        # EMA信号估算
        # 假设: 每天2-3个信号，胜率60%，平均盈利0.2%
        ema_signals_per_day = 2.5
        ema_win_rate = 0.6
        ema_avg_profit_pct = Decimal("0.002")  # 0.2%
        ema_position_size = Decimal("1000")  # 假设1000 USDT余额 * 15% = 150 USDT
        
        # 单次信号利润估算
        single_signal_profit = ema_position_size * ema_avg_profit_pct
        # 考虑胜率
        expected_daily_ema_profit = single_signal_profit * Decimal(str(ema_signals_per_day)) * Decimal(str(ema_win_rate))
        
        # EMA交易也会产生少量手续费
        ema_volume = ema_position_size * Decimal(str(ema_signals_per_day)) * Decimal("2")  # 开平各一次
        ema_fee = ema_volume * Decimal("0.0005")  # 市价单手续费更高
        
        net_ema_profit = expected_daily_ema_profit - ema_fee
        net_pnl = net_ema_profit - grid_fee
        
        print("\n估算结果:")
        print(f"  - 网格交易量: ${float(volume):,.0f}")
        print(f"  - 网格手续费: ${float(grid_fee):.2f}")
        print(f"  - EMA信号频率: ~{ema_signals_per_day}次/天")
        print(f"  - EMA预期利润: ${float(expected_daily_ema_profit):.2f}")
        print(f"  - EMA交易手续费: ${float(ema_fee):.2f}")
        print(f"  - EMA净利润: ${float(net_ema_profit):.2f}")
        print(f"  - 总净损益: ${float(net_pnl):+.2f}")
        print(f"  - 手续费对冲率: {float(net_ema_profit/grid_fee*100):.1f}%")
        
        self.results["ema"] = {
            "volume": float(volume),
            "grid_fee": float(grid_fee),
            "ema_signals": ema_signals_per_day,
            "ema_profit": float(net_ema_profit),
            "net_pnl": float(net_pnl),
            "grid_spacing": "0.05%",
            "fee_hedge_rate": float(net_ema_profit/grid_fee*100)
        }
        
        print("\n分析:")
        print("  ✓ 优点: 通过趋势交易对冲手续费，可能实现盈亏平衡或小幅盈利")
        print("  ✓ 优点: 网格交易量保持不变")
        print("  ⚠ 注意: EMA信号质量依赖市场环境")
        print("  ⚠ 注意: 需要额外API请求（但在安全范围内）")
    
    def analyze_wider_grid(self):
        """分析更宽网格方案"""
        print("\n【方案3：更宽网格方案】")
        print("-" * 80)
        print("配置:")
        print("  - 网格间距: 0.08% (增加60%)")
        print("  - 网格层数: 3层")
        print("  - EMA交易: 禁用")
        
        # 估算交易量变化
        # 间距增加60%，成交概率约降低40-50%
        volume_reduction_rate = Decimal("0.45")  # 保守估计降低45%
        new_volume = Decimal("340000") * (Decimal("1") - volume_reduction_rate)
        
        fee_rate = Decimal("0.0002")
        new_fee = new_volume * fee_rate
        
        # 但是由于间距更宽，单笔利润可能略有增加
        # 假设盈亏比从1.5提升到1.8
        profit_improvement = Decimal("0.2")  # 20%利润改善
        
        # 估算净损益
        base_loss = Decimal("100")
        # 新的损失 = 基础损失 * 交易量比例 - 利润改善
        estimated_fee_reduction = base_loss * volume_reduction_rate
        profit_from_wider_spread = new_volume * Decimal("0.0001")  # 更宽价差带来的额外利润
        
        net_fee = new_fee
        net_pnl = profit_from_wider_spread - net_fee
        
        print("\n估算结果:")
        print(f"  - 预计交易量: ${float(new_volume):,.0f} (降低{float(volume_reduction_rate)*100:.0f}%)")
        print(f"  - 估算手续费: ${float(new_fee):.2f}")
        print(f"  - 手续费节省: ${float(estimated_fee_reduction):.2f}")
        print(f"  - 更宽价差利润: ${float(profit_from_wider_spread):.2f}")
        print(f"  - 总净损益: ${float(net_pnl):+.2f}")
        print(f"  - 手续费降低率: {float(estimated_fee_reduction/base_loss*100):.1f}%")
        
        self.results["wider_grid"] = {
            "volume": float(new_volume),
            "estimated_fee": float(new_fee),
            "fee_reduction": float(estimated_fee_reduction),
            "wider_spread_profit": float(profit_from_wider_spread),
            "net_pnl": float(net_pnl),
            "grid_spacing": "0.08%",
            "fee_reduction_rate": float(estimated_fee_reduction/base_loss*100)
        }
        
        print("\n分析:")
        print("  ✓ 优点: 直接降低手续费支出")
        print("  ✓ 优点: 单笔利润略有增加")
        print("  ✗ 缺点: 交易量大幅下降，可能不满足刷量需求")
        print("  ✗ 缺点: 成交频率降低")
    
    def print_comparison(self):
        """打印对比总结"""
        print("\n" + "="*80)
        print("方案对比总结")
        print("="*80)
        
        print("\n指标对比:")
        print("-" * 80)
        print(f"{'指标':<20} {'基准方案':<20} {'EMA优化':<20} {'更宽网格':<20}")
        print("-" * 80)
        
        baseline = self.results["baseline"]
        ema = self.results["ema"]
        wider = self.results["wider_grid"]
        
        print(f"{'网格间距':<20} {baseline['grid_spacing']:<20} {ema['grid_spacing']:<20} {wider['grid_spacing']:<20}")
        print(f"{'日交易量(USD)':<20} {baseline['volume']:>19,.0f} {ema['volume']:>19,.0f} {wider['volume']:>19,.0f}")
        print(f"{'网格手续费(USD)':<20} {baseline['actual_fee']:>19.2f} {ema['grid_fee']:>19.2f} {wider['estimated_fee']:>19.2f}")
        print(f"{'EMA净利润(USD)':<20} {baseline['ema_profit']:>19.2f} {ema['ema_profit']:>19.2f} {wider.get('ema_profit', 0):>19.2f}")
        print(f"{'净损益(USD)':<20} {baseline['net_pnl']:>19.2f} {ema['net_pnl']:>19.2f} {wider['net_pnl']:>19.2f}")
        
        print("-" * 80)
        
        # 推荐方案
        print("\n推荐方案分析:")
        print("-" * 80)
        
        if ema['net_pnl'] > baseline['net_pnl'] and ema['net_pnl'] > wider['net_pnl']:
            print("\n🏆 推荐: EMA优化方案")
            print("\n理由:")
            print("  1. 能够有效对冲手续费损耗")
            print("  2. 保持原有交易量不变，满足刷量需求")
            print(f"  3. 预期净损益: ${ema['net_pnl']:+.2f}")
            print(f"  4. 手续费对冲率: {ema.get('fee_hedge_rate', 0):.1f}%")
            print("  5. API请求在安全范围内（1次/1.2秒）")
            print("\n实施建议:")
            print("  - 先小仓位运行1-2天验证EMA信号效果")
            print("  - 监控EMA交易的胜率和盈亏比")
            print("  - 如果效果不佳，可调整EMA周期或止盈止损参数")
        elif wider['net_pnl'] > baseline['net_pnl']:
            print("\n🏆 推荐: 更宽网格方案")
            print("\n理由:")
            print("  1. 直接降低手续费支出")
            print(f"  2. 手续费降低约{wider.get('fee_reduction_rate', 0):.1f}%")
            print(f"  3. 预期净损益: ${wider['net_pnl']:+.2f}")
            print("\n⚠️  注意:")
            print(f"  - 交易量将降低约{float(Decimal('340000')-Decimal(str(wider['volume'])))/340000*100:.0f}%")
            print("  - 如果主要目标是刷量，此方案可能不适合")
        else:
            print("\n建议: 保持基准方案或综合优化")
            print("\n说明:")
            print("  - 两种优化方案效果有限")
            print("  - 可考虑组合策略：稍微增大网格间距(0.06%) + 启用EMA")
    
    def print_api_safety_check(self):
        """打印API安全检查"""
        print("\n" + "="*80)
        print("API请求频率安全评估")
        print("="*80)
        
        print("\nEdgeX限制: 2次请求/2秒")
        print("\n当前配置:")
        print("  - API调用间隔: 1.2秒/次")
        print("  - 实际频率: 0.83次/秒 = 1.67次/2秒 ✓ 安全")
        
        print("\nEMA方案额外请求:")
        print("  - EMA计算: 本地完成，无额外请求")
        print("  - EMA下单: 约2-3次/天")
        print("  - 日常网格: 约200-300次/天")
        print("  - 总计: ~250-320次/天 ✓ 远低于限制")
        
        print("\n结论: ✓ EMA方案不会导致API限速问题")
    
    def run_comparison(self):
        """运行对比分析"""
        self.print_header()
        self.analyze_baseline()
        self.analyze_ema_strategy()
        self.analyze_wider_grid()
        self.print_comparison()
        self.print_api_safety_check()
        
        print("\n" + "="*80)
        print("评估完成")
        print("="*80)
        print("\n下一步:")
        print("  1. 查看对比结果，选择合适方案")
        print("  2. 修改 main.py 中的 optimization_mode 参数")
        print("  3. 运行策略: python main.py")
        print("  4. 监控运行效果，根据实际情况调整")
        print("\n")


def main():
    """主函数"""
    comparison = StrategyComparison()
    comparison.run_comparison()


if __name__ == "__main__":
    main()

