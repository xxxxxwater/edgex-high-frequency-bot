# Docker Hub 部署指南

## 前置要求

### 1. 安装 Docker Desktop (macOS)

```bash
# 方法1: 使用 Homebrew 安装
brew install --cask docker

# 方法2: 从官网下载
# 访问: https://www.docker.com/products/docker-desktop/
# 下载并安装 Docker Desktop for Mac
```

安装完成后，启动 Docker Desktop 应用程序。

### 2. 验证 Docker 安装

```bash
docker --version
docker-compose --version
```

## 部署步骤

### 第一步：登录 Docker Hub

```bash
docker login -u pgresearchchris
# 输入您的 Docker Hub 密码
```

### 第二步：构建 Docker 镜像

```bash
cd /Users/christse/edgex-high-frequency-bot

# 构建镜像（标签为 latest）
docker build -t pgresearchchris/edgex-high-frequency-bot:latest .

# 可选：同时添加版本标签
docker build -t pgresearchchris/edgex-high-frequency-bot:v1.0.0 .
```

### 第三步：推送到 Docker Hub

```bash
# 推送 latest 版本
docker push pgresearchchris/edgex-high-frequency-bot:latest

# 如果有版本标签，也推送版本
docker push pgresearchchris/edgex-high-frequency-bot:v1.0.0
```

### 第四步：验证镜像

访问 Docker Hub 查看镜像：
```
https://hub.docker.com/r/pgresearchchris/edgex-high-frequency-bot
```

## 使用部署的镜像

### 方式1：直接运行

```bash
docker run -d \
  --name edgex-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  pgresearchchris/edgex-high-frequency-bot:latest
```

### 方式2：使用 docker-compose

创建 `.env` 文件后：

```bash
docker-compose up -d
```

### 查看日志

```bash
# 查看实时日志
docker logs -f edgex-bot

# 或使用 docker-compose
docker-compose logs -f
```

### 停止容器

```bash
# 直接运行的方式
docker stop edgex-bot
docker rm edgex-bot

# docker-compose 方式
docker-compose down
```

## 镜像管理

### 查看本地镜像

```bash
docker images | grep edgex-high-frequency-bot
```

### 删除本地镜像

```bash
docker rmi pgresearchchris/edgex-high-frequency-bot:latest
```

### 从 Docker Hub 拉取镜像

```bash
docker pull pgresearchchris/edgex-high-frequency-bot:latest
```

## 多平台构建（可选）

如果需要构建支持多个平台的镜像（如 amd64 和 arm64）：

```bash
# 创建并使用 buildx
docker buildx create --name multiplatform --use

# 构建并推送多平台镜像
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t pgresearchchris/edgex-high-frequency-bot:latest \
  --push \
  .
```

## 常见问题

### Q: 构建速度慢？
A: 可以使用国内镜像加速器，编辑 `~/.docker/daemon.json`：
```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://registry.docker-cn.com"
  ]
}
```

### Q: 推送失败？
A: 确保已登录 Docker Hub：
```bash
docker logout
docker login -u pgresearchchris
```

### Q: 镜像过大？
A: 检查 `.dockerignore` 文件，排除不必要的文件：
```
__pycache__/
*.pyc
*.pyo
.git/
.env
logs/
data/
*.log
.DS_Store
```

## 快速部署脚本

创建 `deploy.sh` 脚本：

```bash
#!/bin/bash
set -e

VERSION=${1:-latest}
IMAGE_NAME="pgresearchchris/edgex-high-frequency-bot"

echo "🔨 构建镜像..."
docker build -t $IMAGE_NAME:$VERSION .

echo "📤 推送到 Docker Hub..."
docker push $IMAGE_NAME:$VERSION

if [ "$VERSION" != "latest" ]; then
    echo "🏷️  同时推送 latest 标签..."
    docker tag $IMAGE_NAME:$VERSION $IMAGE_NAME:latest
    docker push $IMAGE_NAME:latest
fi

echo "✅ 部署完成！"
echo "镜像地址: $IMAGE_NAME:$VERSION"
```

使用方法：
```bash
chmod +x deploy.sh
./deploy.sh v1.0.0  # 推送特定版本
./deploy.sh         # 推送 latest
```

## 安全建议

1. **不要在镜像中包含敏感信息**：
   - 使用 `.dockerignore` 排除 `.env` 文件
   - 通过环境变量或 Docker secrets 注入配置

2. **定期更新基础镜像**：
   ```bash
   docker pull python:3.11-slim
   docker build --no-cache -t pgresearchchris/edgex-high-frequency-bot:latest .
   ```

3. **使用版本标签**：
   - 不要只依赖 `latest` 标签
   - 为每个发布版本创建特定标签

4. **扫描安全漏洞**：
   ```bash
   docker scan pgresearchchris/edgex-high-frequency-bot:latest
   ```

