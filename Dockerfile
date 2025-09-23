# 使用官方Rust镜像作为构建环境
FROM rust:1.70-slim-bullseye as builder

# 设置工作目录
WORKDIR /app

# 复制Cargo.toml和Cargo.lock（如果存在）
COPY Cargo.toml ./

# 创建虚拟main.rs来缓存依赖
RUN mkdir src && echo "fn main() {}" > src/main.rs

# 构建依赖（缓存层）
RUN cargo build --release

# 复制源代码
COPY src/ ./src/

# 重新构建应用（使用缓存的依赖）
RUN cargo build --release

# 使用轻量级运行时镜像
FROM debian:bullseye-slim

# 安装必要的运行时依赖
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m -u 1000 appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制二进制文件
COPY --from=builder /app/target/release/edgex-high-frequency-bot /app/

# 复制配置文件（如果有）
COPY --chown=appuser:appuser .env.example /app/

# 设置文件权限
RUN chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 设置环境变量
ENV RUST_LOG=info

# 暴露必要的端口（如果需要）
# EXPOSE 8080

# 设置入口点
ENTRYPOINT ["./edgex-high-frequency-bot"]
