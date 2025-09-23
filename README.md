# EdgeX 高频低波动交易机器人

一个基于Rust开发的高频低波动交易机器人，专为EdgeX交易所设计。该策略通过高频交易实现低波动率的稳定收益。

## 功能特性

-  **高频交易**: 基于价格偏离的快速交易策略
-  **波动率控制**: 实时监控并控制投资组合波动率
-  **性能优化**: 使用Rust语言，高性能低延迟
-  **风险管理**: 内置止损止盈和交易频率控制
-  **实时监控**: 每小时性能报告和交易统计
-  **容器化**: 支持Docker部署
-  **配置灵活**: 支持多币种和参数自定义

## 技术架构

- **语言**: Rust 2025 Edition
- **异步运行时**: Tokio
- **HTTP客户端**: Reqwest
- **WebSocket**: Tokio-tungstenite
- **序列化**: Serde
- **时间处理**: Chrono
- **日志系统**: env_logger

## 快速开始

### 环境要求

- Rust 1.70+ 或 Docker
- EdgeX交易所API密钥

### 1. 克隆项目

```bash
git clone https://github.com/xxxxxwater/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot
```

### 2. 配置环境变量

复制环境变量模板并配置您的API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
EDGEX_API_KEY=your_actual_api_key
EDGEX_SECRET_KEY=your_actual_secret_key
INITIAL_BALANCE=10000.0
SYMBOLS=BTCUSDT,ETHUSDT
```

### 3. 本地运行

#### 使用Cargo运行

```bash
# 调试模式
cargo run

# 发布模式
cargo run --release
```

#### 使用Docker运行

```bash
# 构建镜像
docker build -t edgex-high-frequency-bot .

# 运行容器
docker run -it --env-file .env edgex-high-frequency-bot
```

### 4. Docker Compose部署

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  edgex-bot:
    build: .
    container_name: edgex-high-frequency-bot
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

运行服务：

```bash
docker-compose up -d
```

## 策略说明

### 交易逻辑

1. **信号生成**: 基于价格与移动平均线的偏离度生成交易信号
2. **仓位管理**: 根据波动率和账户余额动态调整仓位大小
3. **风险控制**: 内置止损止盈机制和交易频率限制
4. **波动率监控**: 实时监控投资组合波动率，自动调整交易频率

### 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TARGET_VOLATILITY` | 0.005 | 目标波动率 (0.5%) |
| `BASE_POSITION_SIZE` | 0.001 | 基础仓位比例 (0.1%) |
| `MAX_TRADES_PER_DAY` | 200 | 每日最大交易次数 |
| `MIN_TRADE_INTERVAL` | 5 | 最小交易间隔(秒) |
| `MAX_TRADE_INTERVAL` | 60 | 最大交易间隔(秒) |
| `STOP_LOSS_PCT` | 0.002 | 止损比例 (0.2%) |
| `TAKE_PROFIT_PCT` | 0.002 | 止盈比例 (0.2%) |

## 配置说明

### 环境变量

```env
# 必需配置
EDGEX_API_KEY=your_api_key
EDGEX_SECRET_KEY=your_secret_key

# 策略配置
INITIAL_BALANCE=10000.0
TARGET_VOLATILITY=0.005
BASE_POSITION_SIZE=0.001
MAX_TRADES_PER_DAY=200
MIN_TRADE_INTERVAL=5
MAX_TRADE_INTERVAL=60
STOP_LOSS_PCT=0.002
TAKE_PROFIT_PCT=0.002
SYMBOLS=BTCUSDT,ETHUSDT
TIMEFRAME=1m

# 可选配置
RUST_LOG=info
```

### 交易品种配置

支持多个交易品种，用逗号分隔：

```env
SYMBOLS=BTCUSDT,ETHUSDT,ADAUSDT
```

## 性能监控

机器人每小时输出性能报告：

```
============================================================
高频策略性能报告
============================================================
时间: 2024-01-01 12:00:00
净值: 10050.25 USDT
今日盈亏: 50.25 USDT
波动率: 0.0045 (目标: 0.0050)
波动率比率: 0.90
交易量: 85000.00 / 1000000.00 (8.50%)
交易次数: 45
交易间隔: 8秒
============================================================
```

## Docker镜像使用

### 从Docker Hub拉取

```bash
docker pull your-dockerhub-username/edgex-high-frequency-bot:latest
```

### 运行镜像

```bash
docker run -d \
  --name edgex-bot \
  --env-file .env \
  your-dockerhub-username/edgex-high-frequency-bot:latest
```

### 构建自定义镜像

```bash
# 构建镜像
docker build -t your-username/edgex-high-frequency-bot .

# 推送到Docker Hub
docker push your-username/edgex-high-frequency-bot:latest
```

## 开发指南

### 项目结构

```
src/
├── main.rs          # 程序入口点
├── types.rs         # 数据类型定义
├── edgex_client.rs  # EdgeX API客户端
├── strategy.rs      # 交易策略实现
├── monitor.rs       # 性能监控
└── error.rs         # 错误处理
```

### 添加新的交易策略

1. 在 `strategy.rs` 中实现新的策略逻辑
2. 在 `types.rs` 中添加相关数据结构
3. 在 `main.rs` 中集成新策略

### 测试

```bash
# 运行单元测试
cargo test

# 运行集成测试
cargo test -- --test-threads=1
```

## 风险管理

⚠️ **重要提醒**

- 本策略使用50倍杠杆，风险极高
- 请在测试网充分测试后再投入真实资金
- 建议从小额资金开始，逐步增加
- 实时监控策略表现，及时调整参数

## 故障排除

### 常见问题

1. **API连接失败**
   - 检查API密钥和网络连接
   - 验证EdgeX交易所状态

2. **交易频率过高**
   - 调整 `MIN_TRADE_INTERVAL` 参数
   - 检查波动率设置

3. **内存使用过高**
   - 使用release模式编译
   - 监控日志文件大小

### 日志调试

设置日志级别为debug获取详细日志：

```env
RUST_LOG=debug
```

## 贡献指南

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 免责声明

本软件仅供学习和研究使用，作者不对使用本软件进行交易产生的任何损失负责。使用前请充分了解风险，并在法律允许的范围内使用。

## 联系方式

- 项目地址: [GitHub Repository](https://github.com/xxxxxwater/edgex-high-frequency-bot)
- 问题反馈: [Issues](https://github.com/xxxxxwater/edgex-high-frequency-bot/issues)

---

**注意**: 交易有风险，投资需谨慎！

