# EdgeX网格策略使用指南 (v3.6 & v3.7)

## 📚 目录
- [策略版本对比](#策略版本对比)
- [v3.6 使用指南](#v36-使用指南)
- [v3.7 使用指南](#v37-使用指南)
- [快速开始](#快速开始)
- [参数配置](#参数配置)
- [性能对比](#性能对比)
- [常见问题](#常见问题)

---

## 策略版本对比

| 特性 | v3.5 | v3.6 | v3.7 |
|------|------|------|------|
| **策略类型** | 高频网格 | 宽间距网格+EMA | 多币种网格+EMA |
| **网格层数** | 3层 | 2层 | 3层 |
| **网格间距** | 0.05%-0.072% | 1.2%-1.5% | 1.2% |
| **交易币对** | 4个 | 4个 | 7个 |
| **EMA信号** | 基础 | 优化增强 | 优化增强 |
| **订单刷新** | 90秒 | 120秒 | 120秒 |
| **API安全余量** | 15% | 23% | 8% |
| **目标场景** | 高频交易量 | 低损耗稳健 | 高交易量+多样化 |
| **推荐资金** | 20,000 USDT | 20,000 USDT | 30,000+ USDT |

### 版本选择建议

- **选择v3.6**：追求低损耗、稳健盈利，资金20,000 USDT左右
- **选择v3.7**：追求高交易量、多币种分散，资金30,000+ USDT

---

## v3.6 使用指南

### 核心特点

v3.6是**手续费优化版**，专注于降低交易损耗，适合追求稳健盈利的用户。

#### 关键优化
- ✅ **2层网格结构**：减少33%订单数量
- ✅ **1.2%-1.5%宽间距**：单格利润是手续费的50-62倍
- ✅ **30%净值EMA仓位**：增强趋势盈利能力
- ✅ **0.8%止盈/0.4%止损**：提高盈亏比至2:1
- ✅ **120秒订单刷新**：降低API调用频率

#### 性能指标
- 每百万美金损耗：<73 USDT（v3.5为1000 USDT）
- 利润/手续费比：50-62倍
- 日交易量：约100-150倍净值
- API调用频率：0.77次/秒（安全余量23%）

### 安装运行

#### 1. 环境准备
```bash
# 克隆项目
git clone -b Gridstrategy https://github.com/xxxxxwater/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置API
编辑 `config.py`：
```python
# EdgeX API配置
EDGEX_API_KEY = "your_api_key_here"
EDGEX_ACCOUNT_ID = "your_account_id_here"
EDGEX_USE_TESTNET = False  # True=测试网, False=主网

# 交易币对（v3.6默认4个）
symbols = [
    "BTC-USD",
    "ETH-USD", 
    "SOL-USD",
    "BNB-USD"
]
```

#### 3. 启动策略

**方式1：推荐配置（EMA模式，1.2%间距）**
```bash
python run_strategy_v3.6.py ema
```

**方式2：更宽间距（1.5%间距，更保守）**
```bash
python run_strategy_v3.6.py wider_grid
```

**方式3：基准模式（v3.5兼容）**
```bash
python run_strategy_v3.6.py baseline
```

#### 4. 后台运行
```bash
# 使用nohup后台运行
nohup python run_strategy_v3.6.py ema > v3.6_output.log 2>&1 &

# 查看进程
ps aux | grep python

# 停止策略
killall -9 python
```

### v3.6 参数说明

#### 核心参数（在 `strategy_hft_v3_6.py` 中）

```python
# 网格参数
self.grid_levels = 2                    # 网格层数（每侧）
self.grid_spacing_pct = Decimal("0.012") # 1.2%间距（ema模式）
self.position_size_pct = Decimal("0.10") # 每格仓位10%净值

# EMA参数
self.ema_position_size_pct = Decimal("0.30")  # EMA仓位30%净值
self.ema_take_profit_pct = Decimal("0.008")   # 止盈0.8%
self.ema_stop_loss_pct = Decimal("0.004")     # 止损0.4%
self.ema_min_signal_interval = 900            # 信号间隔15分钟

# 订单管理
self.order_refresh_interval = 120  # 订单刷新120秒
self.api_call_interval = 1.3       # API间隔1.3秒
```

### 实时监控

```bash
# 查看实时日志
tail -f logs/hft_strategy_v3.6_$(date +%Y-%m-%d).log

# 查看最近100行
tail -100 logs/hft_strategy_v3.6_$(date +%Y-%m-%d).log

# 分析交易统计
grep "日累计交易量" logs/hft_strategy_v3.6_*.log | tail -20

# 分析EMA信号
grep "EMA.*信号" logs/hft_strategy_v3.6_*.log | tail -20
```

### v3.6 最佳实践

1. **首次运行**：先使用测试网运行24小时，验证策略逻辑
2. **小资金测试**：主网首次运行建议使用5,000-10,000 USDT测试
3. **参数调优**：运行7天后，根据实际表现微调参数
4. **风控监控**：每日检查持仓占比、挂单数量、日盈亏
5. **定期评估**：每周评估交易量、手续费率、整体盈亏

---

## v3.7 使用指南

### 核心特点

v3.7是**多币种扩展版**，在v3.6基础上增加了更多交易币对，适合追求高交易量和多样化的用户。

#### 关键特性
- ✅ **7个交易币对**：BTC、ETH、SOL、BNB、DOGE、XRP、HYPE
- ✅ **3层网格结构**：提高市场覆盖率
- ✅ **1.2%网格间距**：保持单格高利润
- ✅ **60个最大挂单**：支持多币种同时运行
- ✅ **1.08秒API间隔**：优化API调用频率

#### 性能指标
- 日交易量：约200-300倍净值
- 币种分散度：7个主流币种
- API调用频率：0.93次/秒（安全余量7%）
- 推荐资金：30,000+ USDT

### 安装运行

#### 1. 配置币对
编辑 `config.py`：
```python
# v3.7交易币对（7个）
symbols = [
    "BTC-USD",
    "ETH-USD", 
    "SOL-USD",
    "BNB-USD",
    "DOGE-USD",
    "XRP-USD",
    "HYPE-USD"
]
```

#### 2. 启动策略

**推荐配置（EMA模式）**
```bash
python run_v3.7.py ema
```

**更宽间距（wider_grid模式）**
```bash
python run_v3.7.py wider_grid
```

#### 3. 后台运行
```bash
# 后台运行v3.7
nohup python run_v3.7.py ema > v3.7_output.log 2>&1 &

# 查看日志
tail -f logs/hft_v3.7_$(date +%Y-%m-%d).log
```

### v3.7 参数说明

#### 核心参数（在 `strategy_hft_v3_7.py` 中）

```python
# 网格参数
self.grid_levels = 3                    # 网格层数（每侧）
self.grid_spacing_pct = Decimal("0.012") # 1.2%间距
self.position_size_pct = Decimal("0.08") # 每格仓位8%净值

# EMA参数（同v3.6）
self.ema_position_size_pct = Decimal("0.30")
self.ema_take_profit_pct = Decimal("0.008")
self.ema_stop_loss_pct = Decimal("0.004")

# 订单管理（多币种优化）
self.order_refresh_interval = 120  # 订单刷新120秒
self.api_call_interval = 1.08      # API间隔1.08秒（更激进）
self.max_open_orders = 60          # 最大挂单60个
```

### v3.7 最小订单量

在 `strategy_hft_v3_7.py` 中已配置：
```python
MIN_ORDER_SIZES = {
    "BTC-USD": Decimal("0.001"),
    "ETH-USD": Decimal("0.01"),
    "SOL-USD": Decimal("0.1"),
    "BNB-USD": Decimal("0.01"),
    "DOGE-USD": Decimal("100"),    # 新增
    "XRP-USD": Decimal("10"),      # 新增
    "HYPE-USD": Decimal("10"),     # 新增
}
```

### v3.7 最佳实践

1. **资金要求**：建议至少30,000 USDT，每个币对约4,000-5,000 USDT
2. **API监控**：密切关注API调用频率，避免超限
3. **分批启动**：首次运行可先启动4个币对，稳定后再增加
4. **币对选择**：根据市场热度调整币对，可替换表现不佳的币种
5. **持仓监控**：7个币对同时运行时，总持仓占比需严格控制在50%以内

---

## 快速开始

### 最快5步启动

```bash
# 1. 克隆项目
git clone -b Gridstrategy https://github.com/xxxxxwater/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置API（编辑config.py）
# 填入您的API密钥和账户ID

# 4. 启动策略（选择v3.6或v3.7）
python run_strategy_v3.6.py ema  # v3.6
# 或
python run_v3.7.py ema           # v3.7

# 5. 监控日志
tail -f logs/hft_strategy_v3.6_*.log  # v3.6
# 或
tail -f logs/hft_v3.7_*.log           # v3.7
```

### Docker部署（推荐生产环境）

#### v3.6 Docker
```bash
# 构建镜像
docker build -t edgex-grid-v3.6:latest -f Dockerfile.v3.6 .

# 运行容器
docker run -d \
  --name edgex-v3.6 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config.py:/app/config.py \
  edgex-grid-v3.6:latest ema

# 查看日志
docker logs -f edgex-v3.6
```

#### v3.7 Docker
```bash
# 构建镜像
docker build -t edgex-grid-v3.7:latest -f Dockerfile.v3.7 .

# 运行容器
docker run -d \
  --name edgex-v3.7 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config.py:/app/config.py \
  edgex-grid-v3.7:latest ema

# 查看日志
docker logs -f edgex-v3.7
```

---

## 参数配置

### 通用配置（config.py）

```python
# ===== EdgeX API配置 =====
EDGEX_API_KEY = "your_api_key_here"
EDGEX_SECRET_KEY = "your_secret_key_here"
EDGEX_STARK_PRIVATE_KEY = "your_stark_private_key_here"
EDGEX_ACCOUNT_ID = "your_account_id_here"
EDGEX_USE_TESTNET = False  # True=测试网, False=主网

# ===== 交易币对 =====
# v3.6配置（4个币对）
symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]

# v3.7配置（7个币对）
# symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD", "XRP-USD", "HYPE-USD"]
```

### v3.6 高级配置

如需调整参数，编辑 `strategy_hft_v3_6.py`：

```python
# 调整网格间距（风险偏好）
# 保守：1.5%间距，降低交易频率
self.grid_spacing_pct = Decimal("0.015")

# 激进：1.0%间距，提高交易频率
self.grid_spacing_pct = Decimal("0.010")

# 调整EMA仓位（盈利偏好）
# 保守：20%净值
self.ema_position_size_pct = Decimal("0.20")

# 激进：40%净值
self.ema_position_size_pct = Decimal("0.40")

# 调整止盈止损（风险控制）
# 保守：0.6%止盈 / 0.3%止损
self.ema_take_profit_pct = Decimal("0.006")
self.ema_stop_loss_pct = Decimal("0.003")

# 激进：1.0%止盈 / 0.5%止损
self.ema_take_profit_pct = Decimal("0.010")
self.ema_stop_loss_pct = Decimal("0.005")
```

### v3.7 高级配置

如需调整参数，编辑 `strategy_hft_v3_7.py`：

```python
# 调整网格层数（覆盖率）
# 保守：2层（降低订单数）
self.grid_levels = 2

# 激进：4层（提高覆盖率）
self.grid_levels = 4

# 调整API间隔（速率控制）
# 保守：1.2秒（更安全）
self.api_call_interval = 1.2

# 激进：1.05秒（更快速）
self.api_call_interval = 1.05

# 调整最大挂单数
# 保守：50个
self.max_open_orders = 50

# 激进：80个
self.max_open_orders = 80
```

---

## 性能对比

### 交易量对比（20,000 USDT净值）

| 版本 | 日交易量 | 月交易量 | 手续费成本 | 预期日收益 |
|------|---------|---------|-----------|----------|
| v3.5 | $2.0M | $60M | -$200 | -$100 |
| v3.6 | $2.5M | $75M | -$18 | +$40 |
| v3.7 | $4.0M | $120M | -$30 | +$60 |

### 损耗对比（每百万美金交易量）

| 版本 | 网格损耗 | EMA盈利 | 净损耗/盈利 |
|------|---------|---------|-----------|
| v3.5 | -$294 | +$15 | -$279 |
| v3.6 | -$7 | +$32 | +$25 |
| v3.7 | -$8 | +$15 | +$7 |

### 风险指标对比

| 指标 | v3.5 | v3.6 | v3.7 |
|------|------|------|------|
| 最大持仓占比 | 50% | 50% | 50% |
| 最大挂单数 | 40 | 30 | 60 |
| API安全余量 | 15% | 23% | 7% |
| 单笔最大亏损 | 1% | 1% | 1% |
| 日最大亏损 | 5% | 5% | 5% |

---

## 常见问题

### Q1: v3.6和v3.7应该选择哪个？

**A**: 根据您的资金量和风险偏好：

- **选v3.6（推荐新手）**：
  - 资金20,000 USDT左右
  - 追求稳健低损耗
  - API安全余量更大（23%）
  - 适合长期运行

- **选v3.7（进阶用户）**：
  - 资金30,000+ USDT
  - 追求高交易量
  - 能接受更激进的API调用（7%余量）
  - 适合多样化投资

### Q2: 如何获取EdgeX API密钥？

**A**: 
1. 访问 [EdgeX官网](https://edgex.exchange)
2. 注册并完成KYC
3. 进入账户设置 → API管理
4. 创建新的API密钥
5. 保存API Key、Secret Key和Stark Private Key

### Q3: 测试网和主网如何切换？

**A**: 编辑 `config.py`：

```python
# 测试网
EDGEX_USE_TESTNET = True

# 主网（真实交易）
EDGEX_USE_TESTNET = False
```

建议先在测试网运行48小时，验证策略无误后再切换主网。

### Q4: 如何调整交易币对？

**A**: 编辑 `config.py`：

```python
# 只交易单个币对
symbols = ["BTC-USD"]

# 自定义多个币对
symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]

# v3.7全部币对
symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD", "XRP-USD", "HYPE-USD"]
```

注意：修改币对后需重启策略。

### Q5: 如何停止策略？

**A**: 

```bash
# 直接运行的情况
Ctrl+C

# 后台运行的情况
killall -9 python

# Docker运行的情况
docker stop edgex-v3.6  # 或 edgex-v3.7
```

### Q6: 策略会爆仓吗？

**A**: v3.6和v3.7都有完善的防爆仓机制：

1. **低杠杆**：10倍杠杆，价格需波动10%才会爆仓
2. **持仓限制**：最大50%净值，留有50%安全余量
3. **止损保护**：单笔1%止损，日5%损失限制
4. **动态平仓**：超出限制自动平仓

极端情况（如BTC单日暴跌30%+）下仍有风险，建议设置合理杠杆。

### Q7: 如何评估策略表现？

**A**: 运行7天后，检查以下指标：

```bash
# 1. 查看交易量
grep "日累计交易量" logs/hft_strategy_v3.6_*.log | tail -7

# 2. 查看手续费
grep "日累计手续费" logs/hft_strategy_v3.6_*.log | tail -7

# 3. 查看EMA盈亏
grep "EMA仓位平仓" logs/hft_strategy_v3.6_*.log | tail -20

# 4. 计算7天净盈亏
# 净盈亏 = EMA总盈利 - 网格总手续费
```

**良好表现标准**：
- 日交易量：100-200倍净值（v3.6）或200-300倍（v3.7）
- 手续费率：<0.01%
- 7天净盈利：>0
- 最大回撤：<3%

### Q8: API请求超限怎么办？

**A**: 如果出现`RATE_LIMIT_EXCEEDED`错误：

1. **立即调整参数**（编辑策略文件）：
```python
# 增加API间隔
self.api_call_interval = 1.5  # 从1.3增加到1.5

# 增加订单刷新间隔
self.order_refresh_interval = 150  # 从120增加到150
```

2. **重启策略**
3. **监控日志**，确认无超限错误

### Q9: 如何优化盈利？

**A**: 可以尝试以下调整：

1. **提高EMA仓位**（增加趋势盈利）：
```python
self.ema_position_size_pct = Decimal("0.35")  # 从30%提高到35%
```

2. **调整止盈目标**（提高单笔收益）：
```python
self.ema_take_profit_pct = Decimal("0.010")  # 从0.8%提高到1.0%
```

3. **增加币对**（仅v3.7，提高交易量）：
```python
symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD", "XRP-USD", "HYPE-USD", "AVAX-USD"]
```

4. **优化网格间距**（平衡频率与利润）：
```python
self.grid_spacing_pct = Decimal("0.010")  # 从1.2%降至1.0%（更频繁，但需监控手续费）
```

### Q10: 如何备份和恢复？

**A**: 

**备份**：
```bash
# 备份配置
cp config.py config.py.backup

# 备份日志
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/

# 备份策略文件
cp strategy_hft_v3_6.py strategy_hft_v3_6.py.backup
```

**恢复**：
```bash
# 恢复配置
cp config.py.backup config.py

# 恢复日志
tar -xzf logs_backup_YYYYMMDD.tar.gz

# 恢复策略文件
cp strategy_hft_v3_6.py.backup strategy_hft_v3_6.py
```

---

## ⚠️ 风险提示

1. **交易风险**：加密货币交易存在高风险，可能导致本金损失
2. **策略风险**：历史表现不代表未来收益，市场变化可能导致策略失效
3. **技术风险**：网络中断、API错误、服务器故障可能影响交易
4. **API风险**：v3.7的API调用更激进（7%余量），需密切监控
5. **资金管理**：建议使用闲置资金，不超过总资产的20-30%

### 安全建议

- ✅ 先在测试网运行48小时
- ✅ 主网首次运行使用小额资金（5,000-10,000 USDT）
- ✅ 设置合理的止损和日亏损限制
- ✅ 定期监控策略表现和风险指标
- ✅ 不要使用过高杠杆（建议≤10倍）
- ✅ 保持API密钥安全，不要分享给任何人

---

## 📞 支持与反馈

- **GitHub仓库**: [edgex-high-frequency-bot](https://github.com/xxxxxwater/edgex-high-frequency-bot)
- **Issues**: [提交问题](https://github.com/xxxxxwater/edgex-high-frequency-bot/issues)
- **Email**: chris@pgresearch.org
- **Website**: [PG Research](https://pgresearch.org)

### 文档更新

- v3.6文档最后更新：2025-10-08
- v3.7文档最后更新：2025-10-08
- 策略版本：v3.6.0 / v3.7.0

---

## 📄 License

MIT License - 详见 LICENSE 文件

**免责声明**：本项目仅供学习和研究使用，使用本项目进行实盘交易的任何损失由使用者自行承担。作者不对任何直接或间接损失负责。

---

**祝交易顺利！** 🚀

