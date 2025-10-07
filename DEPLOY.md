# EdgeX高频交易机器人 - 部署指南

本文档提供详细的部署步骤，帮助您快速部署EdgeX高频交易机器人。

## 📋 前提条件

### 1. EdgeX账户准备

1. 注册EdgeX账户：
   - 测试网：https://testnet.edgex.exchange
   - 主网：https://pro.edgex.exchange

2. 获取API凭证：
   - 登录EdgeX账户
   - 进入 **账户设置** → **API管理**
   - 点击 **创建API密钥**
   - 保存以下信息（请妥善保管）：
     - `API Key`
     - `Secret Key`
     - `Stark Private Key`
     - `Account ID`

### 2. 系统要求

- **操作系统**：Linux / macOS / Windows
- **Python版本**：3.11 或更高
- **内存**：最少 2GB RAM
- **存储**：最少 1GB 可用空间
- **网络**：稳定的互联网连接

## 🚀 本地部署

### 方式一：直接运行

#### 步骤1：克隆项目

```bash
git clone https://github.com/yourusername/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot
```

#### 步骤2：创建虚拟环境

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

#### 步骤3：安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 步骤4：配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env  # 或使用你喜欢的编辑器
```

填入你的EdgeX凭证：
```env
EDGEX_API_KEY=your_api_key_here
EDGEX_SECRET_KEY=your_secret_key_here
EDGEX_STARK_PRIVATE_KEY=your_stark_private_key_here
EDGEX_ACCOUNT_ID=your_account_id_here
EDGEX_TESTNET=true
```

#### 步骤5：验证配置

```bash
# 查看可用合约列表
python utils.py --list-contracts

# 验证账户访问
python utils.py --verify-account
```

#### 步骤6：启动机器人

```bash
# 方式1：直接运行
python main.py

# 方式2：使用启动脚本
python start.py

# 方式3：后台运行
nohup python main.py > bot.log 2>&1 &
```

### 方式二：使用systemd（Linux推荐）

#### 创建服务文件

```bash
sudo nano /etc/systemd/system/edgex-bot.service
```

内容：
```ini
[Unit]
Description=EdgeX High Frequency Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/edgex-high-frequency-bot
Environment="PATH=/path/to/edgex-high-frequency-bot/venv/bin"
ExecStart=/path/to/edgex-high-frequency-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 启动服务

```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start edgex-bot

# 设置开机自启
sudo systemctl enable edgex-bot

# 查看状态
sudo systemctl status edgex-bot

# 查看日志
journalctl -u edgex-bot -f
```

## 🐳 Docker部署

### 方式一：本地构建

#### 步骤1：构建镜像

```bash
# 进入项目目录
cd edgex-high-frequency-bot

# 构建Docker镜像
docker build -t edgex-bot:latest .
```

#### 步骤2：配置环境变量

```bash
# 创建.env文件
cp .env.example .env
# 编辑并填入你的配置
nano .env
```

#### 步骤3：运行容器

```bash
# 使用docker run
docker run -d \
  --name edgex-trading-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  edgex-bot:latest

# 或使用docker-compose（推荐）
docker-compose up -d
```

#### 步骤4：管理容器

```bash
# 查看日志
docker-compose logs -f

# 停止容器
docker-compose down

# 重启容器
docker-compose restart

# 查看容器状态
docker-compose ps
```

### 方式二：从DockerHub拉取

#### 步骤1：拉取镜像

```bash
docker pull yourusername/edgex-high-frequency-bot:latest
```

#### 步骤2：运行

```bash
docker run -d \
  --name edgex-trading-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  yourusername/edgex-high-frequency-bot:latest
```

## 📤 推送到DockerHub

### 步骤1：登录DockerHub

```bash
docker login
```

### 步骤2：标记镜像

```bash
docker tag edgex-bot:latest yourusername/edgex-high-frequency-bot:latest
docker tag edgex-bot:latest yourusername/edgex-high-frequency-bot:v1.0.0
```

### 步骤3：推送镜像

```bash
# 推送latest版本
docker push yourusername/edgex-high-frequency-bot:latest

# 推送版本标签
docker push yourusername/edgex-high-frequency-bot:v1.0.0
```

### 步骤4：验证

访问 https://hub.docker.com/r/yourusername/edgex-high-frequency-bot 查看镜像。

## ☁️ 云服务器部署

### AWS EC2

```bash
# 1. 启动EC2实例（Ubuntu 22.04，t3.small或更高）
# 2. SSH连接到实例
ssh -i your-key.pem ubuntu@your-ec2-ip

# 3. 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 4. 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. 克隆项目
git clone https://github.com/yourusername/edgex-high-frequency-bot.git
cd edgex-high-frequency-bot

# 6. 配置环境变量
cp .env.example .env
nano .env

# 7. 启动
docker-compose up -d
```

### Google Cloud Platform

```bash
# 1. 创建Compute Engine实例
# 2. SSH连接
gcloud compute ssh your-instance-name

# 3. 后续步骤与AWS相同
```

### 阿里云/腾讯云

```bash
# 1. 购买ECS/CVM实例
# 2. SSH连接
ssh root@your-server-ip

# 3. 后续步骤与AWS相同
```

## 🔧 配置优化

### 1. 日志轮转

创建 `/etc/logrotate.d/edgex-bot`:

```
/path/to/edgex-high-frequency-bot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

### 2. 资源限制

编辑 `docker-compose.yml`：

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### 3. 网络优化

```bash
# 设置DNS
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

# 优化TCP参数
sysctl -w net.ipv4.tcp_keepalive_time=600
sysctl -w net.ipv4.tcp_keepalive_intvl=60
```

## 📊 监控和告警

### 1. 基础监控

```bash
# 查看CPU和内存使用
docker stats edgex-trading-bot

# 查看日志
tail -f logs/trading_bot_*.log
```

### 2. 配置告警

使用钉钉/企业微信/Telegram等平台配置告警（需要额外开发）。

## 🔄 更新部署

### Docker部署更新

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建镜像
docker-compose build

# 3. 重启容器
docker-compose down
docker-compose up -d
```

### 本地部署更新

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 更新依赖
pip install -r requirements.txt --upgrade

# 3. 重启服务
sudo systemctl restart edgex-bot
```

## ❗ 故障排查

### 问题1：机器人无法启动

```bash
# 检查日志
docker-compose logs

# 验证配置
python utils.py --verify-account
```

### 问题2：连接超时

```bash
# 检查网络
ping edgex.exchange

# 测试API
curl https://testnet.edgex.exchange/api/v1/public/time
```

### 问题3：内存不足

```bash
# 增加swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 🔐 安全建议

1. **保护API密钥**：
   - 不要将 `.env` 文件提交到Git
   - 使用环境变量管理敏感信息
   - 定期轮换API密钥

2. **服务器安全**：
   - 配置防火墙，只开放必要端口
   - 使用SSH密钥而非密码登录
   - 定期更新系统和软件包

3. **监控告警**：
   - 设置异常交易告警
   - 监控账户余额变化
   - 记录所有重要操作

## 📞 技术支持

- GitHub Issues: https://github.com/yourusername/edgex-high-frequency-bot/issues
- EdgeX官方文档: https://docs.edgex.exchange

---

**部署完成！** 🎉

现在你的EdgeX高频交易机器人应该已经在运行了。建议先在测试网运行一段时间，确认策略表现符合预期后再切换到主网。

