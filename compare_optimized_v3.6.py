"""
EdgeX策略优化对比 v3.6 - 改进版
展示优化后的EMA参数效果

@version 3.6 Enhanced
@date 2025-10-08
"""

from decimal import Decimal


def print_comparison():
    """打印优化方案对比"""
    
    print("\n" + "="*90)
    print("EdgeX高频策略手续费优化方案对比 v3.6 - 改进版")
    print("="*90)
    
    print("\n📊 当前状况:")
    print("  - 日交易量: 34万美金")
    print("  - 手续费损耗: 100 USDT")
    print("  - 目标: 通过优化降低或对冲手续费损耗")
    
    print("\n" + "="*90)
    
    # 基准方案
    print("\n【方案1: 基准方案 - v3.5原配置】")
    print("-" * 90)
    
    baseline_volume = Decimal("340000")
    baseline_fee = Decimal("100")
    baseline_pnl = -baseline_fee
    
    print(f"  网格间距: 0.05%")
    print(f"  日交易量: ${float(baseline_volume):,.0f}")
    print(f"  手续费: ${float(baseline_fee):.2f}")
    print(f"  净损益: ${float(baseline_pnl):+.2f}")
    print(f"\n  ✓ 优点: 交易量充足")
    print(f"  ✗ 缺点: 每日损耗$100")
    
    # EMA优化方案（改进版）
    print("\n【方案2: EMA优化方案 - 改进版】⭐ 推荐")
    print("-" * 90)
    
    ema_volume = Decimal("340000")  # 保持不变
    ema_grid_fee = Decimal("100")
    
    # 改进后的EMA参数
    # 仓位: 25%净值 (假设余额1000U = 250U)
    # 止盈: 0.6%, 止损: 0.3%
    # 信号频率: 1.5次/天 (提高间隔到10分钟，减少虚假信号)
    # 胜率: 65% (更高质量信号)
    
    balance = Decimal("1000")  # 假设余额
    ema_position_pct = Decimal("0.25")
    ema_position_size = balance * ema_position_pct  # 250U
    
    signals_per_day = Decimal("1.5")
    win_rate = Decimal("0.65")
    avg_profit_pct = Decimal("0.006")  # 0.6% 止盈
    avg_loss_pct = Decimal("0.003")    # 0.3% 止损
    
    # 预期盈利 = (盈利次数 * 盈利额) - (亏损次数 * 亏损额)
    win_count = signals_per_day * win_rate
    loss_count = signals_per_day * (Decimal("1") - win_rate)
    
    win_amount = win_count * ema_position_size * avg_profit_pct
    loss_amount = loss_count * ema_position_size * avg_loss_pct
    
    gross_ema_profit = win_amount - loss_amount
    
    # EMA交易手续费（市价单，taker费率约0.05%）
    ema_trade_volume = ema_position_size * signals_per_day * Decimal("2")  # 开平各一次
    ema_trade_fee = ema_trade_volume * Decimal("0.0005")
    
    net_ema_profit = gross_ema_profit - ema_trade_fee
    total_pnl = -ema_grid_fee + net_ema_profit
    
    hedge_rate = (net_ema_profit / ema_grid_fee) * Decimal("100")
    
    print(f"  网格间距: 0.05% (保持不变)")
    print(f"  EMA参数: 快线9 / 慢线21")
    print(f"  EMA仓位: 25%净值 (${float(ema_position_size):.0f})")
    print(f"  止盈/止损: +0.6% / -0.3%")
    print(f"  信号间隔: 10分钟 (提高质量)")
    print()
    print(f"  网格交易量: ${float(ema_volume):,.0f}")
    print(f"  网格手续费: ${float(ema_grid_fee):.2f}")
    print()
    print(f"  EMA信号频率: {float(signals_per_day)}次/天")
    print(f"  EMA预期胜率: {float(win_rate)*100:.0f}%")
    print(f"  EMA毛利润: ${float(gross_ema_profit):.2f}")
    print(f"  EMA交易手续费: ${float(ema_trade_fee):.2f}")
    print(f"  EMA净利润: ${float(net_ema_profit):+.2f}")
    print()
    print(f"  📊 总净损益: ${float(total_pnl):+.2f}")
    print(f"  📊 手续费对冲率: {float(hedge_rate):.1f}%")
    print(f"  📊 损耗降低: {float((baseline_pnl - total_pnl) / baseline_pnl * 100):.1f}%")
    print()
    print(f"  ✓ 优点: 保持交易量，对冲手续费")
    print(f"  ✓ 优点: 预期能对冲{float(hedge_rate):.0f}%手续费")
    print(f"  ✓ 优点: API请求安全")
    print(f"  ⚠ 注意: 需要验证实际胜率")
    
    # 更宽网格方案
    print("\n【方案3: 更宽网格方案】")
    print("-" * 90)
    
    wider_reduction = Decimal("0.45")
    wider_volume = baseline_volume * (Decimal("1") - wider_reduction)
    wider_fee_rate = Decimal("0.0002")
    wider_fee = wider_volume * wider_fee_rate
    
    # 更宽价差带来的额外利润
    wider_spread_profit = wider_volume * Decimal("0.0001")
    wider_pnl = wider_spread_profit - wider_fee
    
    fee_reduction = baseline_fee - wider_fee
    
    print(f"  网格间距: 0.08% (增加60%)")
    print(f"  预计交易量: ${float(wider_volume):,.0f} (↓{float(wider_reduction)*100:.0f}%)")
    print(f"  估算手续费: ${float(wider_fee):.2f}")
    print(f"  手续费节省: ${float(fee_reduction):.2f}")
    print(f"  更宽价差利润: ${float(wider_spread_profit):.2f}")
    print(f"  📊 总净损益: ${float(wider_pnl):+.2f}")
    print(f"  📊 损耗降低: {float((baseline_pnl - wider_pnl) / baseline_pnl * 100):.1f}%")
    print()
    print(f"  ✓ 优点: 直接降低手续费{float(fee_reduction/baseline_fee*100):.0f}%")
    print(f"  ✗ 缺点: 交易量降低{float(wider_reduction*100):.0f}%")
    
    # 混合方案
    print("\n【方案4: 混合优化方案】🏆 最佳平衡")
    print("-" * 90)
    
    # 网格间距0.06%，交易量降低约20%
    hybrid_grid_spacing = Decimal("0.06")
    hybrid_volume_reduction = Decimal("0.20")
    hybrid_grid_volume = baseline_volume * (Decimal("1") - hybrid_volume_reduction)
    hybrid_grid_fee = hybrid_grid_volume * wider_fee_rate
    
    # EMA参数同方案2，但因为网格费用更低，总体更优
    hybrid_ema_profit = net_ema_profit  # EMA利润不变
    hybrid_total_pnl = -hybrid_grid_fee + hybrid_ema_profit
    
    hybrid_improvement = (baseline_pnl - hybrid_total_pnl) / abs(baseline_pnl) * Decimal("100")
    
    print(f"  网格间距: 0.06% (轻微增大)")
    print(f"  EMA交易: 启用 (同方案2)")
    print(f"  EMA仓位: 25%净值")
    print()
    print(f"  网格交易量: ${float(hybrid_grid_volume):,.0f} (↓{float(hybrid_volume_reduction)*100:.0f}%)")
    print(f"  网格手续费: ${float(hybrid_grid_fee):.2f}")
    print(f"  EMA净利润: ${float(hybrid_ema_profit):+.2f}")
    print(f"  📊 总净损益: ${float(hybrid_total_pnl):+.2f}")
    print(f"  📊 改善幅度: {float(hybrid_improvement):.1f}%")
    print()
    print(f"  ✓ 优点: 双重优化，效果最佳")
    print(f"  ✓ 优点: 仍保持80%交易量")
    print(f"  ✓ 优点: 预期损耗降低{float(hybrid_improvement):.0f}%")
    
    # 对比表格
    print("\n" + "="*90)
    print("📊 方案对比总结")
    print("="*90)
    print()
    print(f"{'指标':<20} {'基准方案':<18} {'EMA优化':<18} {'更宽网格':<18} {'混合方案':<18}")
    print("-" * 90)
    print(f"{'网格间距':<20} {'0.05%':<18} {'0.05%':<18} {'0.08%':<18} {'0.06%':<18}")
    print(f"{'日交易量':<20} {'$340,000':<18} {'$340,000':<18} {f'${float(wider_volume):,.0f}':<18} {f'${float(hybrid_grid_volume):,.0f}':<18}")
    print(f"{'网格手续费':<20} {'$100.00':<18} {'$100.00':<18} {f'${float(wider_fee):.2f}':<18} {f'${float(hybrid_grid_fee):.2f}':<18}")
    print(f"{'EMA净利润':<20} {'$0.00':<18} {f'${float(net_ema_profit):+.2f}':<18} {'$0.00':<18} {f'${float(hybrid_ema_profit):+.2f}':<18}")
    print(f"{'净损益':<20} {f'${float(baseline_pnl):+.2f}':<18} {f'${float(total_pnl):+.2f}':<18} {f'${float(wider_pnl):+.2f}':<18} {f'${float(hybrid_total_pnl):+.2f}':<18}")
    print(f"{'改善幅度':<20} {'基准':<18} {f'{float((baseline_pnl-total_pnl)/abs(baseline_pnl)*100):.1f}%':<18} {f'{float((baseline_pnl-wider_pnl)/abs(baseline_pnl)*100):.1f}%':<18} {f'{float(hybrid_improvement):.1f}%':<18}")
    print("-" * 90)
    
    # 推荐
    print("\n" + "="*90)
    print("🎯 推荐方案")
    print("="*90)
    
    print("\n🥇 首选: 方案4 (混合优化方案)")
    print("   - 预期净损益: ${:.2f} (改善{:.1f}%)".format(float(hybrid_total_pnl), float(hybrid_improvement)))
    print("   - 保持80%交易量")
    print("   - 网格手续费降低 + EMA利润对冲")
    print("   - 综合效果最优")
    
    print("\n🥈 备选: 方案2 (EMA优化)")
    print("   - 如果必须保持100%交易量")
    print("   - 预期净损益: ${:.2f} (改善{:.1f}%)".format(
        float(total_pnl), 
        float((baseline_pnl-total_pnl)/abs(baseline_pnl)*100)
    ))
    print("   - 对冲{:.0f}%手续费".format(float(hedge_rate)))
    
    print("\n🥉 备选: 方案3 (更宽网格)")
    print("   - 如果可以接受交易量降低45%")
    print("   - 预期净损益: ${:.2f} (改善{:.1f}%)".format(
        float(wider_pnl),
        float((baseline_pnl-wider_pnl)/abs(baseline_pnl)*100)
    ))
    print("   - 直接降低手续费")
    
    # API安全性
    print("\n" + "="*90)
    print("🔒 API请求频率安全评估")
    print("="*90)
    
    print("\n  EdgeX限制: 2次请求/2秒")
    print("  当前配置: 1次/1.2秒 = 1.67次/2秒 ✓ 安全")
    print()
    print("  各方案日请求量:")
    print("    - 基准方案: ~250次/天")
    print("    - EMA优化:  ~260次/天 (+EMA下单3-5次)")
    print("    - 更宽网格: ~150次/天")
    print("    - 混合方案: ~210次/天")
    print()
    print("  ✓ 所有方案都在安全范围内")
    
    # 实施建议
    print("\n" + "="*90)
    print("📋 实施建议")
    print("="*90)
    
    print("\n阶段1: 验证阶段 (1-2天)")
    print("  1. 运行方案2 (EMA优化) 或方案4 (混合优化)")
    print("  2. 小仓位运行，观察EMA信号质量")
    print("  3. 记录: 信号次数、胜率、实际盈亏")
    
    print("\n阶段2: 优化阶段 (3-5天)")
    print("  4. 如果EMA胜率 > 60%: 继续使用")
    print("  5. 如果EMA胜率 < 50%: 调整参数或禁用")
    print("  6. 根据实际数据微调网格间距")
    
    print("\n阶段3: 稳定运行 (长期)")
    print("  7. 选定最优方案持续运行")
    print("  8. 每周评估性能")
    print("  9. 根据市场变化适时调整")
    
    # 运行方法
    print("\n" + "="*90)
    print("🚀 运行方法")
    print("="*90)
    
    print("\n  1. 查看对比分析:")
    print("     python compare_optimized_v3.6.py")
    print()
    print("  2. 运行策略:")
    print("     python main_v3.6.py")
    print("     (然后选择模式: 1=基准, 2=EMA, 3=更宽网格)")
    print()
    print("  3. 查看实时日志:")
    print("     tail -f logs/hft_strategy_v3.6_*.log")
    
    print("\n" + "="*90)
    print("分析完成")
    print("="*90)
    print()


if __name__ == "__main__":
    print_comparison()

