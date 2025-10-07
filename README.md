# 高频算法机器 (Python版 v3.4)

本框架基于EdgeX交易所的多币种高频算法机器机器人，其他PerpDEX换SDK和修改即可，使用Python实现，支持BTC、ETH、SOL、BNB等多个交易对的24小时自动化并发交易。**超快速启动版本 - 仅需5分钟即可开始交易**。

## 📋 目录

- [特性](#特性)
- [策略说明](#策略说明)
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [Docker部署](#docker部署)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

## ✨ 特性

### 核心功能
- ✅ **多币种高频交易策略**：支持BTC、ETH、SOL、BNB等多个交易对
- ✅ **并发交易**：同时监控和交易多个币种，分散风险
- ✅ **24小时交易**：加密货币市场全天候运行
- ✅ **超快启动**：仅需5分钟K线数据即可开始交易（优化75%）
- ✅ **固定仓位管理**：每个币种独立5%仓位，简单高效
- ✅ **严格风险控制**：止盈止损自动管理（±0.4%）
- ✅ **智能下单量检查**：各币种独立最小下单量（BTC:0.001, ETH:0.02, SOL:0.3, BNB:0.01）

### 技术特性
- 🚀 **异步架构**：基于asyncio的高性能异步处理
- 🔐 **安全签名**：使用StarkEx签名适配器
- 📊 **实时监控**：性能报告和交易统计，支持多交易对分组显示
- 🐳 **Docker支持**：一键部署到DockerHub
- 📝 **完整日志**：详细的交易和错误日志
- 🔄 **合约ID缓存**：智能合约映射，提升性能

## 📈 策略说明

### 策略核心

本策略是**均线偏离回归策略**（v3.4 - 超快速启动版），基于以下逻辑：

1. **信号生成**：
   - 计算5周期移动平均线（MA5）
   - 当前价格（1周期MA）偏离MA5超过阈值(0.2%)时生成信号
   - 价格高于MA → 做空（预期回归）
   - 价格低于MA → 做多（预期回归）
   - **超快启动**：仅需5根K线（5分钟）即可开始交易

2. **仓位管理**：
   - 基础仓位：账户余额的5%（每个币种独立计算）
   - 固定仓位：无波动率调整，简单高效
   - 最小下单量：各币种独立配置（BTC:0.001, ETH:0.02, SOL:0.3, BNB:0.01）
   - 最大仓位：不超过账户余额的50%
   - 多交易对风险分散：4个币种同时交易，有效降低单一币种风险

3. **风险控制**：
   - 止盈：0.4%
   - 止损：0.4%
   - 无波动率限制：连续交易，不暂停

### 策略参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 基础仓位比例 | 5% | 每次开仓占用的账户百分比（固定） |
| 杠杆倍数 | 50x | 合约杠杆 |
| 止盈百分比 | 0.4% | 触发止盈的价格变化 |
| 止损百分比 | 0.4% | 触发止损的价格变化 |
| 中期均线周期 | 5 | MA5均线计算周期 |
| 短期均线周期 | 1 | MA1均线（当前价格） |
| 偏离阈值 | 0.2% | 触发交易的价格偏离度 |
| 启动时间 | 5分钟 | 需要5根K线数据 |

## 💻 系统要求

- Python 3.11+
- 2GB+ 内存
- 稳定的网络连接
- EdgeX交易所账户（测试网或主网）

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑.env文件，填入你的EdgeX账户信息
vim .env
```

必填配置：
```env
EDGEX_API_KEY=your_api_key_here
EDGEX_SECRET_KEY=your_secret_key_here
EDGEX_STARK_PRIVATE_KEY=your_stark_private_key_here
EDGEX_ACCOUNT_ID=your_account_id_here
```

### 4. 运行机器人

```bash
# 直接运行
python main.py

# 或使用启动脚本
python start.py
```

## ⚙️ 配置说明

### 环境变量详解

#### EdgeX API配置
- `EDGEX_API_KEY`: EdgeX API密钥（必填）
- `EDGEX_SECRET_KEY`: EdgeX Secret密钥（必填）
- `EDGEX_STARK_PRIVATE_KEY`: Stark私钥，用于L2交易签名（必填）
- `EDGEX_ACCOUNT_ID`: EdgeX账户ID（必填）

#### 网络配置
- `EDGEX_TESTNET`: 是否使用测试网 (true/false，默认true)

#### 交易配置
- `EDGEX_SYMBOLS`: 交易对列表，逗号分隔（默认：BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT）
  - 支持单个交易对：`EDGEX_SYMBOLS=SOL-USDT`
  - 支持多个交易对：`EDGEX_SYMBOLS=BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT`
- `EDGEX_BASE_POSITION_SIZE`: 基础仓位比例（默认：0.05，即5%，每个币种独立计算，固定不调整）
- `EDGEX_LEVERAGE`: 杠杆倍数（默认：50）
- `EDGEX_TAKE_PROFIT_PCT`: 止盈百分比（默认：0.004，即0.4%）
- `EDGEX_STOP_LOSS_PCT`: 止损百分比（默认：0.004，即0.4%）

#### 风控配置
- `EDGEX_MIN_ORDER_SIZE`: 最小下单量配置（各币种自动识别）
  - BTC: 0.001
  - ETH: 0.02
  - SOL: 0.3
  - BNB: 0.01
  - 默认: 0.05（未配置的币种）
- `EDGEX_MAX_POSITION_PCT`: 最大仓位比例（默认：0.5，即50%）

#### 交易频率
- `EDGEX_MIN_TRADE_INTERVAL`: 最小交易间隔毫秒（默认：5000）
- `EDGEX_MAX_TRADE_INTERVAL`: 最大交易间隔毫秒（默认：60000）

#### 监控配置
- `EDGEX_PERFORMANCE_REPORT_INTERVAL`: 性能报告间隔秒（默认：300）
- `EDGEX_LOG_LEVEL`: 日志级别（DEBUG/INFO/WARNING/ERROR，默认：INFO）

### 合约ID映射

EdgeX使用数字合约ID，常见映射：

| 合约ID | 交易对 | 说明 |
|--------|--------|------|
| 10000001 | BTC-USDT | 比特币 |
| 10000002 | ETH-USDT | 以太坊 |
| 10000003 | SOL-USDT | Solana |
| 10000004 | BNB-USDT | BNB |

获取完整列表：
```python
# 在代码中调用
metadata = await client.get_metadata()
contracts = metadata.get("data", {}).get("contractList", [])
```

## 🐳 Docker部署

### 构建镜像

```bash
# 构建Docker镜像
docker build -t edgex-high-frequency-bot:latest .

# 或使用docker-compose构建
docker-compose build
```

### 运行容器

```bash
# 使用docker-compose运行（推荐）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止容器
docker-compose down
```

### 推送到DockerHub

```bash
# 登录DockerHub
docker login

# 标记镜像
docker tag edgex-high-frequency-bot:latest pgresearchchris/edgex-high-frequency-bot:latest

# 推送镜像
docker push pgresearchchris/edgex-high-frequency-bot:latest
```

### 从DockerHub拉取并运行

```bash
# 拉取镜像
docker pull pgresearchchris/edgex-high-frequency-bot:latest

# 运行
docker run -d \
  --name edgex-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  pgresearchchris/edgex-high-frequency-bot:latest
```

## 📁 项目结构

```
edgex-high-frequency-bot/
├── sdk/                        # EdgeX Python SDK
│   └── edgex_sdk/             # SDK源码
├── config.py                   # 配置管理
├── edgex_client.py            # EdgeX API客户端封装
├── strategy.py                # 高频交易策略
├── monitor.py                 # 性能监控
├── websocket_client.py        # WebSocket客户端
├── main.py                    # 主程序入口
├── types.py                   # 数据类型定义
├── requirements.txt           # Python依赖
├── .env.example              # 配置模板
├── .gitignore                # Git忽略文件
├── Dockerfile                # Docker构建文件
├── docker-compose.yml        # Docker Compose配置
└── README.md                 # 项目文档
```

## 📊 性能监控

机器人会定期（默认5分钟）输出性能报告：

```
======================================================================
多币种高频策略性能报告 (v3.4 - 超快速启动版)
======================================================================
时间: 2025-10-06 12:00:00
净值: 1050.23 USDT
今日盈亏: 50.23 USDT
交易量: 45000.00 / 50000.00 (90.00%)
交易次数: 125
交易间隔: 5秒
胜率: 65.00%
盈利交易: 81
亏损交易: 44
活跃仓位: 3

持仓详情:
  BTC-USDT: LONG | 数量: 0.015000 | 入场: 68500.00
  ETH-USDT: SHORT | 数量: 0.250000 | 入场: 3250.00
  SOL-USDT: LONG | 数量: 5.500000 | 入场: 145.00
======================================================================
```

## 🔧 常见问题

### Q: 如何获取EdgeX API密钥？

A: 
1. 注册EdgeX账户：https://edgex.exchange
2. 进入账户设置 → API管理
3. 创建新的API密钥
4. 保存API Key、Secret Key和Stark Private Key

### Q: 测试网和主网有什么区别？

A:
- **测试网**：使用虚拟资金，用于测试策略，无真实风险
- **主网**：使用真实资金，有真实盈亏

建议先在测试网验证策略后再使用主网。

### Q: 最小资金要求是多少？

A: 
根据多币种交易，建议最小账户余额（安全系数已提升至2倍）：
- **单交易对**（如仅SOL）：约$100 USDT
  - SOL价格 × 0.3 × 安全系数(2) ≈ $100
- **多交易对**（推荐4个币种）：约$400-600 USDT
  - 每个币种约需$100-150 USDT
  - 建议余额 > $500 USDT以确保有足够资金同时交易多个币种

资金计算公式（安全系数2倍）：
- BTC: 价格 × 0.001 × 2
- ETH: 价格 × 0.02 × 2
- SOL: 价格 × 0.3 × 2
- BNB: 价格 × 0.01 × 2

### Q: 如何调整策略参数？

A: 
编辑`.env`文件中的相关配置，然后重启机器人：
```bash
# 调整仓位为10%（每个币种）
EDGEX_BASE_POSITION_SIZE=0.10

# 调整止盈止损为1%
EDGEX_TAKE_PROFIT_PCT=0.01
EDGEX_STOP_LOSS_PCT=0.01

# 只交易特定币种
EDGEX_SYMBOLS=BTC-USDT,ETH-USDT

# 或只交易单个币种
EDGEX_SYMBOLS=SOL-USDT
```

### Q: 如何查看日志？

A:
- 控制台输出：实时显示INFO级别日志
- 文件日志：`logs/trading_bot_YYYY-MM-DD.log`
- Docker日志：`docker-compose logs -f`

### Q: 机器人崩溃了怎么办？

A:
1. 检查日志文件找到错误原因
2. 验证.env配置是否正确
3. 确认网络连接正常
4. 使用docker-compose自动重启：
   ```bash
   docker-compose up -d --force-recreate
   ```

### Q: 如何停止机器人？

A:
```bash
# 直接运行的情况
Ctrl+C

# Docker运行的情况
docker-compose down
```

## ⚠️ 风险提示

1. **交易风险**：加密货币交易存在高风险，可能导致资金损失
2. **策略风险**：历史表现不代表未来收益
3. **技术风险**：网络中断、API错误等可能影响交易
4. **建议**：
   - 先在测试网充分测试
   - 使用小额资金开始
   - 设置合理的风控参数
   - 定期监控机器人状态

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📮 联系方式

- GitHub: https://github.com/xxxxxwater/edgex-high-frequency-bot
- Issues: https://github.com/xxxxxwater/edgex-high-frequency-bot/issues
- Email: https://pgresearch.org、chris@pgresearch.org


## 📚 参考资料

- [EdgeX官方文档](https://docs.edgex.exchange)
- [EdgeX Python SDK](https://github.com/edgex-Tech/edgex-python-sdk)
- [StarkWare文档](https://docs.starkware.co/)

---

**免责声明**：本项目仅供学习和研究使用，使用本项目进行实盘交易的任何损失由使用者自行承担。

