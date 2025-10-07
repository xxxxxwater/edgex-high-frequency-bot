# Docker 自动化配置指南

## 🎯 概述

本指南介绍如何在服务器上使用 Docker 自动化部署 EdgeX 高频交易机器人，支持通过环境变量或配置文件管理账户信息。

---

## 🚀 快速开始

### 方式 1：使用环境变量（推荐用于服务器）

```bash
docker run -d \
  --name edgex-bot \
  --restart unless-stopped \
  -e EDGEX_ACCOUNT_ID="你的账户ID" \
  -e EDGEX_STARK_PRIVATE_KEY="你的Stark私钥" \
  -e EDGEX_PUBLIC_KEY="你的公钥" \
  -e EDGEX_PUBLIC_KEY_Y_COORDINATE="你的公钥Y坐标" \
  -e EDGEX_TESTNET=false \
  -e EDGEX_SYMBOLS="BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT" \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  pgresearchchris/edgex-high-frequency-bot:latest
```

### 方式 2：使用配置文件

```bash
# 1. 创建配置文件
cat > bot-config.env << 'EOF'
EDGEX_ACCOUNT_ID=你的账户ID
EDGEX_STARK_PRIVATE_KEY=你的Stark私钥
EDGEX_PUBLIC_KEY=你的公钥
EDGEX_PUBLIC_KEY_Y_COORDINATE=你的公钥Y坐标
EDGEX_TESTNET=false
EDGEX_SYMBOLS=BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT
EOF

# 2. 运行容器
docker run -d \
  --name edgex-bot \
  --restart unless-stopped \
  -v $(pwd)/bot-config.env:/app/.env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  pgresearchchris/edgex-high-frequency-bot:latest
```

### 方式 3：使用 docker-compose（推荐用于生产）

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  edgex-bot:
    image: pgresearchchris/edgex-high-frequency-bot:latest
    container_name: edgex-trading-bot
    restart: unless-stopped
    
    # 方式 A: 通过环境变量配置
    environment:
      EDGEX_ACCOUNT_ID: "你的账户ID"
      EDGEX_STARK_PRIVATE_KEY: "你的Stark私钥"
      EDGEX_PUBLIC_KEY: "你的公钥"
      EDGEX_PUBLIC_KEY_Y_COORDINATE: "你的公钥Y坐标"
      EDGEX_TESTNET: "false"
      EDGEX_SYMBOLS: "BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT"
      EDGEX_LEVERAGE: "50"
      EDGEX_BASE_POSITION_SIZE: "0.05"
    
    # 方式 B: 通过配置文件（取消注释使用）
    # env_file:
    #   - ./bot-config.env
    
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      # - ./bot-config.env:/app/.env  # 如果使用配置文件挂载
    
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

运行：
```bash
docker-compose up -d
docker-compose logs -f
```

---

## 📝 配置参数说明

### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `EDGEX_ACCOUNT_ID` | EdgeX 账户 ID | `667221775494415325` |
| `EDGEX_STARK_PRIVATE_KEY` | Stark 私钥 | `0x1234...` |
| `EDGEX_PUBLIC_KEY` | 公钥 | `0x5678...` |
| `EDGEX_PUBLIC_KEY_Y_COORDINATE` | 公钥 Y 坐标 | `0x9abc...` |

### 可选参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `EDGEX_TESTNET` | 是否使用测试网 | `false` |
| `EDGEX_SYMBOLS` | 交易对（逗号分隔） | `BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT` |
| `EDGEX_LEVERAGE` | 杠杆倍数 | `50` |
| `EDGEX_BASE_POSITION_SIZE` | 基础仓位比例 | `0.05` (5%) |
| `EDGEX_TAKE_PROFIT_PCT` | 止盈比例 | `0.004` (0.4%) |
| `EDGEX_STOP_LOSS_PCT` | 止损比例 | `0.004` (0.4%) |
| `EDGEX_MIN_ORDER_SIZE` | 最小下单量 | `0.3` |
| `EDGEX_LOG_LEVEL` | 日志级别 | `INFO` |

---

## 🔧 高级用法

### 1. 创建配置管理脚本

在服务器上创建一个配置管理脚本 `deploy-bot.sh`：

```bash
#!/bin/bash

# EdgeX 交易机器人自动化部署脚本

set -e

# 配置变量
DOCKER_IMAGE="pgresearchchris/edgex-high-frequency-bot:latest"
CONTAINER_NAME="edgex-trading-bot"
CONFIG_FILE="./bot-config.env"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}EdgeX 交易机器人部署脚本${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}未找到配置文件，创建新配置...${NC}"
    
    read -p "EdgeX 账户ID: " ACCOUNT_ID
    read -p "Stark 私钥: " STARK_KEY
    read -p "公钥: " PUBLIC_KEY
    read -p "公钥 Y 坐标: " PUBLIC_KEY_Y
    read -p "使用测试网? (y/n): " TESTNET
    
    TESTNET_VALUE="false"
    if [ "$TESTNET" = "y" ]; then
        TESTNET_VALUE="true"
    fi
    
    cat > "$CONFIG_FILE" << EOF
EDGEX_ACCOUNT_ID=$ACCOUNT_ID
EDGEX_STARK_PRIVATE_KEY=$STARK_KEY
EDGEX_PUBLIC_KEY=$PUBLIC_KEY
EDGEX_PUBLIC_KEY_Y_COORDINATE=$PUBLIC_KEY_Y
EDGEX_TESTNET=$TESTNET_VALUE
EDGEX_SYMBOLS=BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT
EDGEX_LEVERAGE=50
EDGEX_BASE_POSITION_SIZE=0.05
EDGEX_LOG_LEVEL=INFO
EOF
    
    echo -e "${GREEN}✅ 配置文件已创建: $CONFIG_FILE${NC}"
fi

# 停止并删除旧容器
if docker ps -a | grep -q $CONTAINER_NAME; then
    echo -e "${YELLOW}停止旧容器...${NC}"
    docker stop $CONTAINER_NAME || true
    docker rm $CONTAINER_NAME || true
fi

# 拉取最新镜像
echo -e "${YELLOW}拉取最新镜像...${NC}"
docker pull $DOCKER_IMAGE

# 创建日志和数据目录
mkdir -p logs data

# 启动容器
echo -e "${YELLOW}启动容器...${NC}"
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  --env-file $CONFIG_FILE \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  $DOCKER_IMAGE

# 等待启动
sleep 3

# 检查状态
if docker ps | grep -q $CONTAINER_NAME; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}✅ 部署成功！${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo "容器状态:"
    docker ps | grep $CONTAINER_NAME
    echo ""
    echo "查看日志:"
    echo "  docker logs -f $CONTAINER_NAME"
    echo ""
else
    echo -e "${RED}❌ 部署失败${NC}"
    echo "查看错误日志:"
    echo "  docker logs $CONTAINER_NAME"
    exit 1
fi
```

使用方法：
```bash
chmod +x deploy-bot.sh
./deploy-bot.sh
```

### 2. 使用环境变量文件模板

创建 `.env.template` 文件：

```bash
# EdgeX 账户配置（必填）
EDGEX_ACCOUNT_ID=
EDGEX_STARK_PRIVATE_KEY=
EDGEX_PUBLIC_KEY=
EDGEX_PUBLIC_KEY_Y_COORDINATE=

# 网络配置
EDGEX_TESTNET=false

# 交易配置
EDGEX_SYMBOLS=BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT
EDGEX_LEVERAGE=50
EDGEX_BASE_POSITION_SIZE=0.05

# 策略参数
EDGEX_TAKE_PROFIT_PCT=0.004
EDGEX_STOP_LOSS_PCT=0.004
EDGEX_TARGET_VOLATILITY=0.60

# 风控配置
EDGEX_MIN_ORDER_SIZE=0.3
EDGEX_MAX_POSITION_PCT=0.5

# 日志级别
EDGEX_LOG_LEVEL=INFO
```

使用时复制并填写：
```bash
cp .env.template bot-config.env
nano bot-config.env  # 填写实际配置
```

### 3. 多实例部署

在同一服务器上运行多个策略实例：

```bash
# 实例 1: 主网高频策略
docker run -d \
  --name edgex-bot-mainnet \
  -e EDGEX_ACCOUNT_ID="账户1" \
  -e EDGEX_STARK_PRIVATE_KEY="私钥1" \
  -e EDGEX_PUBLIC_KEY="公钥1" \
  -e EDGEX_PUBLIC_KEY_Y_COORDINATE="Y坐标1" \
  -e EDGEX_TESTNET=false \
  -v $(pwd)/logs-mainnet:/app/logs \
  pgresearchchris/edgex-high-frequency-bot:latest

# 实例 2: 测试网策略
docker run -d \
  --name edgex-bot-testnet \
  -e EDGEX_ACCOUNT_ID="账户2" \
  -e EDGEX_STARK_PRIVATE_KEY="私钥2" \
  -e EDGEX_PUBLIC_KEY="公钥2" \
  -e EDGEX_PUBLIC_KEY_Y_COORDINATE="Y坐标2" \
  -e EDGEX_TESTNET=true \
  -v $(pwd)/logs-testnet:/app/logs \
  pgresearchchris/edgex-high-frequency-bot:latest
```

---

## 🔍 监控和管理

### 查看日志

```bash
# 实时日志
docker logs -f edgex-trading-bot

# 最近 100 行
docker logs --tail 100 edgex-trading-bot

# 从某个时间开始
docker logs --since 10m edgex-trading-bot
```

### 查看状态

```bash
# 容器状态
docker ps | grep edgex

# 资源使用
docker stats edgex-trading-bot

# 详细信息
docker inspect edgex-trading-bot
```

### 管理操作

```bash
# 停止
docker stop edgex-trading-bot

# 启动
docker start edgex-trading-bot

# 重启
docker restart edgex-trading-bot

# 更新镜像
docker pull pgresearchchris/edgex-high-frequency-bot:latest
docker stop edgex-trading-bot
docker rm edgex-trading-bot
# 然后重新运行

# 查看配置
docker exec edgex-trading-bot env | grep EDGEX
```

---

## 🛠️ 故障排除

### 问题 1: 缺少 Crypto 模块

**错误信息：**
```
ModuleNotFoundError: No module named 'Crypto'
```

**解决方案：**
已在最新镜像中修复（添加了 `pycryptodome`）。请更新镜像：
```bash
docker pull pgresearchchris/edgex-high-frequency-bot:latest
```

### 问题 2: 配置文件未找到

**错误信息：**
```
❌ 错误: 未找到配置！
```

**解决方案：**
确保提供了环境变量或配置文件：
```bash
# 方式 1: 环境变量
docker run -e EDGEX_ACCOUNT_ID=xxx ...

# 方式 2: 配置文件
docker run -v /path/to/.env:/app/.env ...
```

### 问题 3: 容器启动后立即退出

**检查日志：**
```bash
docker logs edgex-trading-bot
```

**常见原因：**
1. 配置参数缺失或错误
2. 账户余额不足
3. API 密钥无效

### 问题 4: 无法连接到 EdgeX API

**检查：**
1. 网络连接是否正常
2. API 密钥是否正确
3. 是否选择了正确的网络（主网/测试网）

```bash
# 测试网络连接
docker exec edgex-trading-bot ping -c 3 pro.edgex.exchange
```

---

## 📊 日志分析

### 日志目录结构

```
logs/
├── runtime.log          # 运行时日志
├── strategy.log         # 策略日志
└── performance.log      # 性能报告
```

### 常用日志命令

```bash
# 查看策略执行
tail -f logs/strategy.log

# 查看性能报告
tail -f logs/performance.log

# 搜索错误
grep "ERROR" logs/runtime.log

# 查看交易信号
grep "信号生成" logs/strategy.log
```

---

## 🔐 安全最佳实践

1. **保护配置文件**
   ```bash
   chmod 600 bot-config.env
   ```

2. **使用 Docker Secrets（Swarm 模式）**
   ```bash
   echo "你的私钥" | docker secret create stark_key -
   ```

3. **定期轮换密钥**
   - 建议每 30-90 天更换一次 API 密钥

4. **监控异常活动**
   ```bash
   # 设置日志告警
   docker logs -f edgex-trading-bot | grep -i "error\|warning"
   ```

5. **限制容器权限**
   ```bash
   docker run --security-opt="no-new-privileges:true" ...
   ```

---

## 🚀 自动化部署示例

### GitHub Actions 部署

创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy Trading Bot

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/edgex-bot
            docker pull pgresearchchris/edgex-high-frequency-bot:latest
            docker-compose down
            docker-compose up -d
```

### Systemd 服务（使用 docker-compose）

创建 `/etc/systemd/system/edgex-bot.service`：

```ini
[Unit]
Description=EdgeX Trading Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/edgex-bot
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable edgex-bot
sudo systemctl start edgex-bot
sudo systemctl status edgex-bot
```

---

## 📚 相关文档

- [Docker 部署详细指南](./DOCKER_DEPLOY.md)
- [快速开始指南](./DOCKER_QUICKSTART.md)
- [项目 README](./README.md)
- [部署成功报告](./DEPLOYMENT_SUCCESS.md)

---

## 💡 技巧和建议

1. **使用命名卷（Named Volumes）**
   ```bash
   docker volume create edgex-logs
   docker volume create edgex-data
   
   docker run -v edgex-logs:/app/logs -v edgex-data:/app/data ...
   ```

2. **设置资源限制**
   ```bash
   docker run --memory="2g" --cpus="2" ...
   ```

3. **健康检查**
   ```bash
   docker run --health-cmd="python -c 'import sys; sys.exit(0)'" \
     --health-interval=30s \
     --health-timeout=10s \
     --health-retries=3 ...
   ```

4. **日志轮转**
   ```bash
   docker run --log-opt max-size=10m --log-opt max-file=3 ...
   ```

---

## 🎯 总结

现在您可以：

✅ 使用环境变量快速部署
✅ 使用配置文件管理多个实例
✅ 通过 docker-compose 实现生产级部署
✅ 自动化配置和部署流程
✅ 监控和管理运行中的机器人

**快速命令备忘：**

```bash
# 一键部署
docker run -d --name edgex-bot \
  -e EDGEX_ACCOUNT_ID="xxx" \
  -e EDGEX_STARK_PRIVATE_KEY="yyy" \
  -e EDGEX_PUBLIC_KEY="zzz" \
  -e EDGEX_PUBLIC_KEY_Y_COORDINATE="www" \
  -v $(pwd)/logs:/app/logs \
  pgresearchchris/edgex-high-frequency-bot:latest

# 查看日志
docker logs -f edgex-bot

# 停止
docker stop edgex-bot
```

祝交易顺利！ 🚀

