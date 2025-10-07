# Docker 快速开始指南

## 📦 方式一：使用已发布的镜像（推荐）

### 1. 准备配置文件

创建 `.env` 文件（参考 `.env.example`）：

```bash
cp .env.example .env
# 编辑 .env 文件，填入您的配置
```

### 2. 拉取并运行

```bash
# 拉取镜像
docker pull pgresearchchris/edgex-high-frequency-bot:latest

# 运行容器
docker run -d \
  --name edgex-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  pgresearchchris/edgex-high-frequency-bot:latest
```

### 3. 查看运行状态

```bash
# 查看容器状态
docker ps

# 查看实时日志
docker logs -f edgex-bot

# 查看最近100行日志
docker logs --tail 100 edgex-bot
```

### 4. 停止和管理

```bash
# 停止容器
docker stop edgex-bot

# 启动容器
docker start edgex-bot

# 重启容器
docker restart edgex-bot

# 删除容器
docker rm -f edgex-bot
```

---

## 🚀 方式二：使用 docker-compose（推荐用于生产环境）

### 1. 准备文件

确保有以下文件：
- `docker-compose.yml` ✅ (已有)
- `.env` (需要创建)

```bash
cp .env.example .env
# 编辑 .env 文件
```

### 2. 启动服务

```bash
# 启动（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps
```

### 3. 管理服务

```bash
# 停止服务
docker-compose stop

# 启动服务
docker-compose start

# 重启服务
docker-compose restart

# 停止并删除容器
docker-compose down

# 更新镜像并重启
docker-compose pull
docker-compose up -d
```

---

## 🔧 方式三：本地构建并运行

### 1. 构建镜像

```bash
cd /Users/christse/edgex-high-frequency-bot

# 构建
docker build -t pgresearchchris/edgex-high-frequency-bot:latest .
```

### 2. 运行

```bash
docker run -d \
  --name edgex-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  pgresearchchris/edgex-high-frequency-bot:latest
```

---

## 📤 发布到 Docker Hub

### 自动化部署脚本

```bash
# 发布 latest 版本
./deploy_docker.sh

# 发布特定版本
./deploy_docker.sh v1.0.0
```

### 手动部署

```bash
# 登录
docker login -u pgresearchchris

# 构建
docker build -t pgresearchchris/edgex-high-frequency-bot:latest .

# 推送
docker push pgresearchchris/edgex-high-frequency-bot:latest
```

---

## 🔍 常用调试命令

```bash
# 进入容器内部
docker exec -it edgex-bot bash

# 查看容器资源占用
docker stats edgex-bot

# 查看容器详细信息
docker inspect edgex-bot

# 复制文件到容器
docker cp file.txt edgex-bot:/app/

# 从容器复制文件
docker cp edgex-bot:/app/logs/runtime.log ./
```

---

## ⚠️ 重要提示

### 环境变量配置

确保 `.env` 文件包含所有必需的配置：

```env
# EdgeX API 配置
EDGEX_BASE_URL=https://pro.edgex.exchange
EDGEX_API_KEY=your_api_key
EDGEX_API_SECRET=your_api_secret
EDGEX_ACCOUNT_ID=your_account_id

# 交易配置
SYMBOLS=BTC-USDT,ETH-USDT,SOL-USDT
LEVERAGE=50
BASE_POSITION_SIZE=0.05

# 策略配置
DEVIATION_THRESHOLD=0.002
STOP_LOSS_PERCENTAGE=0.01
TAKE_PROFIT_PERCENTAGE=0.02
```

### 数据持久化

日志和数据文件会保存在宿主机的以下目录：
- `./logs/` - 日志文件
- `./data/` - 数据文件

### 资源限制

默认配置：
- CPU: 0.5-2 核心
- 内存: 512MB-2GB

可在 `docker-compose.yml` 中调整。

### 安全建议

1. ⚠️ **不要**将 `.env` 文件提交到 Git
2. ⚠️ **不要**在 Dockerfile 中硬编码敏感信息
3. ✅ 定期更新镜像：`docker pull pgresearchchris/edgex-high-frequency-bot:latest`
4. ✅ 监控容器日志和资源使用

---

## 🆘 故障排除

### 容器无法启动

```bash
# 查看详细日志
docker logs edgex-bot

# 检查配置
docker exec edgex-bot env
```

### 连接问题

```bash
# 检查网络
docker network ls
docker network inspect bridge

# 测试API连接
docker exec edgex-bot curl -I https://pro.edgex.exchange
```

### 清理镜像

```bash
# 删除未使用的镜像
docker image prune -a

# 删除特定镜像
docker rmi pgresearchchris/edgex-high-frequency-bot:latest
```

---

## 📚 更多信息

- 详细部署指南: `DOCKER_DEPLOY.md`
- 项目文档: `README.md`
- 部署说明: `DEPLOY.md`

---

## 🎯 快速命令参考

```bash
# 一键启动（使用 Docker Hub 镜像）
docker-compose up -d && docker-compose logs -f

# 一键停止
docker-compose down

# 更新并重启
docker-compose pull && docker-compose up -d

# 查看实时日志
docker-compose logs -f --tail 100

# 重启服务
docker-compose restart
```

