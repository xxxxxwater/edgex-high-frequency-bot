# EdgeX高频做市网格策略

[![GitHub stars](https://img.shields.io/github/stars/xxxxxwater/edgex-high-frequency-bot.svg)](https://github.com/xxxxxwater/edgex-high-frequency-bot/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/xxxxxwater/edgex-high-frequency-bot.svg)](https://github.com/xxxxxwater/edgex-high-frequency-bot/network)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

专为EdgeX交易所设计的高频做市网格策略，包含v3.6手续费优化版和v3.7多币种扩展版。

## 🌟 版本特性

### v3.6 - 手续费优化版（推荐新手）
- ✅ **2层网格结构**：减少订单数量，降低交易频率
- ✅ **1.2%-1.5%宽间距**：单格利润是手续费的50-62倍
- ✅ **优化EMA信号**：30%净值仓位，0.8%止盈/0.4%止损
- ✅ **损耗降低93%**：从1000 USDT/百万美金降至<73 USDT
- ✅ **4个交易对**：BTC、ETH、SOL、BNB
- ✅ **API安全余量23%**：确保不会超限

**适合场景**：追求稳健盈利，资金20,000 USDT左右

### v3.7 - 多币种扩展版（进阶用户）
- ✅ **7个交易对**：BTC、ETH、SOL、BNB、DOGE、XRP、HYPE
- ✅ **3层网格结构**：提高市场覆盖率
- ✅ **高交易量**：日交易量200-300倍净值
- ✅ **多样化投资**：分散风险，捕捉更多机会
- ✅ **API安全余量7%**：更激进的调用频率

**适合场景**：追求高交易量，资金30,000+ USDT

## 📊 性能对比

| 指标 | v3.5 | v3.6 | v3.7 |
|------|------|------|------|
| 网格层数 | 3层 | 2层 | 3层 |
| 网格间距 | 0.05%-0.072% | 1.2%-1.5% | 1.2% |
| 交易币对 | 4个 | 4个 | 7个 |
| 日交易量 | $2.0M | $2.5M | $4.0M |
| 每百万美金损耗 | $279 | +$25（盈利）| +$7（盈利） |
| API安全余量 | 15% | 23% | 7% |
| 推荐资金 | 20K USDT | 20K USDT | 30K+ USDT |

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone -b Gridstrategy https://github.com/xxxxxwater/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置API
复制配置模板并填入您的信息：
```bash
cp config.py.example config.py
```

编辑 `config.py`：
```python
config = Config(
    account_id=YOUR_ACCOUNT_ID,           # 您的EdgeX账户ID
    stark_private_key="YOUR_STARK_KEY",   # 您的Stark私钥
    testnet=True,                         # 建议先用测试网
    symbols=["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]
)
```

### 4. 启动策略

#### 启动v3.6（推荐）
```bash
# EMA模式（1.2%间距，推荐）
python run_strategy_v3.6.py ema

# 更宽间距（1.5%间距，更保守）
python run_strategy_v3.6.py wider_grid

# 基准模式（v3.5兼容）
python run_strategy_v3.6.py baseline
```

#### 启动v3.7（进阶）
首先修改 `config.py` 添加更多币对：
```python
symbols=["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD", "XRP-USD", "HYPE-USD"]
```

然后启动：
```bash
# EMA模式
python run_v3.7.py ema

# 更宽间距
python run_v3.7.py wider_grid
```

### 5. 监控运行
```bash
# 查看实时日志
tail -f logs/hft_strategy_v3.6_$(date +%Y-%m-%d).log

# 或v3.7
tail -f logs/hft_v3.7_$(date +%Y-%m-%d).log
```

## 📖 完整文档

- **[网格策略完整指南](GRID_STRATEGY_GUIDE.md)** - v3.6和v3.7详细使用说明
- **[v3.6详细文档](README_v3.6.md)** - v3.6策略架构和参数说明
- **[参数优化分析](参数超优化分析_v3.6_真实费率.md)** - 优化方案对比
- **[方案C说明](方案C优化说明.md)** - 保守优化方案

## 🔧 核心文件说明

```
edgex-high-frequency-bot/
├── config.py.example          # 配置模板（复制为config.py）
├── .gitignore                 # Git忽略文件（已排除config.py）
│
├── strategy_hft_v3_6.py       # v3.6策略核心文件
├── run_strategy_v3.6.py       # v3.6启动脚本
├── main_v3.6.py               # v3.6主程序
│
├── strategy_hft_v3_7.py       # v3.7策略核心文件
├── run_v3.7.py                # v3.7启动脚本
│
├── edgex_client.py            # EdgeX API客户端
├── edgex_types.py             # 数据类型定义
├── requirements.txt           # Python依赖
│
├── GRID_STRATEGY_GUIDE.md     # 完整使用指南
├── README_v3.6.md             # v3.6详细文档
└── edgex-python-sdk/          # EdgeX Python SDK
```

## 💡 使用建议

### 新手推荐流程
1. **测试网验证**（48小时）
   - 设置 `testnet=True`
   - 启动 `python run_strategy_v3.6.py ema`
   - 观察策略运行和日志输出

2. **小资金测试**（7天）
   - 切换到主网 `testnet=False`
   - 使用5,000-10,000 USDT测试
   - 评估实际表现

3. **正式运行**
   - 根据测试结果调整参数
   - 使用推荐资金量（20,000 USDT）
   - 定期监控和优化

### 版本选择建议
- **选v3.6**：稳健为主，低损耗，API安全余量大
- **选v3.7**：激进风格，高交易量，多币种分散

## 📈 监控指标

### 每日检查
```bash
# 查看交易统计
grep "日累计交易量" logs/hft_strategy_v3.6_*.log | tail -7

# 查看手续费
grep "日累计手续费" logs/hft_strategy_v3.6_*.log | tail -7

# 查看EMA盈亏
grep "EMA仓位平仓" logs/hft_strategy_v3.6_*.log | tail -20
```

### 关键指标
- **日交易量**：100-200倍净值（v3.6）或200-300倍（v3.7）
- **手续费率**：<0.01%
- **7天净盈利**：应为正值
- **最大回撤**：<3%净值

## ⚠️ 风险提示

1. **交易风险**：加密货币交易存在高风险，可能导致本金损失
2. **策略风险**：历史表现不代表未来收益
3. **技术风险**：网络中断、API错误可能影响交易
4. **API风险**：v3.7的API调用更激进，需密切监控

### 安全建议
- ✅ 先在测试网运行48小时
- ✅ 主网首次使用小额资金
- ✅ 不要使用过高杠杆（建议≤10倍）
- ✅ 定期备份配置和日志
- ✅ 保护好API密钥，不要分享

## 🛠️ 常见问题

### Q: 如何获取EdgeX API密钥？
访问 [EdgeX官网](https://edgex.exchange)，注册并在账户设置中创建API密钥。

### Q: 最小资金要求？
- v3.6：建议20,000 USDT
- v3.7：建议30,000+ USDT
- 测试：可用更小金额

### Q: 如何停止策略？
```bash
# 直接运行
Ctrl+C

# 后台运行
killall -9 python
```

### Q: 策略会爆仓吗？
有完善的风控机制：
- 低杠杆（10倍）
- 持仓限制（50%净值）
- 止损保护（1%单笔，5%日亏损）
- 动态平仓

更多问题请查看 [完整指南](GRID_STRATEGY_GUIDE.md)。

## 📊 参数调整

### v3.6参数优化
编辑 `strategy_hft_v3_6.py`：

```python
# 调整网格间距（风险偏好）
self.grid_spacing_pct = Decimal("0.012")  # 1.2%标准，1.5%保守，1.0%激进

# 调整EMA仓位（盈利偏好）
self.ema_position_size_pct = Decimal("0.30")  # 30%标准，20%保守，40%激进

# 调整止盈止损
self.ema_take_profit_pct = Decimal("0.008")   # 0.8%
self.ema_stop_loss_pct = Decimal("0.004")     # 0.4%
```

### v3.7参数优化
编辑 `strategy_hft_v3_7.py`：

```python
# 调整网格层数
self.grid_levels = 3  # 3层标准，2层保守，4层激进

# 调整API间隔（速率控制）
self.api_call_interval = 1.08  # 1.08秒标准，1.2秒保守

# 调整最大挂单数
self.max_open_orders = 60  # 60个标准，50个保守，80个激进
```

## 🔄 更新日志

### v3.7 (2025-10-08)
- 新增7个币对支持
- 优化API调用频率
- 增强多币种管理

### v3.6 (2025-10-08)
- 损耗降低93%
- 2层网格结构
- 1.2%-1.5%宽间距
- 优化EMA参数
- 确保单格利润>50倍手续费

### v3.5 (2025-10-07)
- 初始版本
- 3层网格
- 基础EMA信号

## 📞 支持与反馈

- **GitHub**: [edgex-high-frequency-bot](https://github.com/xxxxxwater/edgex-high-frequency-bot)
- **Issues**: [提交问题](https://github.com/xxxxxwater/edgex-high-frequency-bot/issues)
- **Email**: chris@pgresearch.org
- **Website**: [PG Research](https://pgresearch.org)

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**免责声明**：本项目仅供学习和研究使用。使用本项目进行实盘交易的任何损失由使用者自行承担。作者不对任何直接或间接损失负责。

**祝交易顺利！** 🚀

