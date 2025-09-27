# 使用特定版本的Rust镜像作为构建环境（避免latest版本不兼容）
FROM rust:1.82 AS builder

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

# 使用Alpine Linux作为运行时镜像（更轻量、更稳定）
FROM alpine:latest

# 安装必要的运行时依赖
RUN apk add --no-cache \
    ca-certificates \
    libgcc

# 创建非root用户
RUN adduser -D -u 1000 appuser

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

# 设置入口点
ENTRYPOINT ["./edgex-high-frequency-bot"]
