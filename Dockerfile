# 使用Python 3.11官方镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 复制项目文件
COPY . .

# 创建日志目录和数据目录
RUN mkdir -p logs data

# 添加执行权限
RUN chmod +x docker-entrypoint.sh config_manager.py

# 设置数据卷
VOLUME ["/app/logs", "/app/data"]

# 暴露端口（如果需要）
# EXPOSE 8000

# 使用入口脚本
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# 默认命令
CMD ["python", "main.py"]

