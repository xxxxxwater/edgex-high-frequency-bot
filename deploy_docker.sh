#!/bin/bash

# EdgeX高频交易机器人 - Docker Hub部署脚本
# 用户名: pgresearchchris

set -e

# 配置
DOCKER_USERNAME="pgresearchchris"
IMAGE_NAME="edgex-high-frequency-bot"
FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME"
VERSION=${1:-latest}

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}EdgeX 交易机器人 Docker 部署${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ 错误: Docker 未安装${NC}"
    echo ""
    echo "请先安装 Docker Desktop:"
    echo "  方法1: brew install --cask docker"
    echo "  方法2: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker 已安装: $(docker --version)"
echo ""

# 检查Docker是否运行
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ 错误: Docker 未运行${NC}"
    echo ""
    echo "请启动 Docker Desktop 应用程序"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker 正在运行"
echo ""

# 检查是否已登录
if ! docker info 2>/dev/null | grep -q "Username: $DOCKER_USERNAME"; then
    echo -e "${YELLOW}📝 登录 Docker Hub...${NC}"
    docker login -u $DOCKER_USERNAME
    echo ""
fi

echo -e "${GREEN}✓${NC} 已登录 Docker Hub: $DOCKER_USERNAME"
echo ""

# 构建镜像
echo -e "${YELLOW}🔨 构建 Docker 镜像...${NC}"
echo "镜像名称: $FULL_IMAGE_NAME:$VERSION"
echo ""

docker build -t $FULL_IMAGE_NAME:$VERSION .

echo ""
echo -e "${GREEN}✓${NC} 镜像构建完成"
echo ""

# 如果不是latest，也打上latest标签
if [ "$VERSION" != "latest" ]; then
    echo -e "${YELLOW}🏷️  添加 latest 标签...${NC}"
    docker tag $FULL_IMAGE_NAME:$VERSION $FULL_IMAGE_NAME:latest
    echo -e "${GREEN}✓${NC} 标签添加完成"
    echo ""
fi

# 推送到Docker Hub
echo -e "${YELLOW}📤 推送镜像到 Docker Hub...${NC}"
echo ""

docker push $FULL_IMAGE_NAME:$VERSION

if [ "$VERSION" != "latest" ]; then
    docker push $FULL_IMAGE_NAME:latest
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 部署成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "镜像地址:"
echo "  - $FULL_IMAGE_NAME:$VERSION"
if [ "$VERSION" != "latest" ]; then
    echo "  - $FULL_IMAGE_NAME:latest"
fi
echo ""
echo "Docker Hub 页面:"
echo "  https://hub.docker.com/r/$DOCKER_USERNAME/$IMAGE_NAME"
echo ""
echo "使用方法:"
echo "  docker pull $FULL_IMAGE_NAME:$VERSION"
echo "  docker run -d --name edgex-bot --env-file .env $FULL_IMAGE_NAME:$VERSION"
echo ""
echo "或使用 docker-compose:"
echo "  docker-compose up -d"
echo ""

