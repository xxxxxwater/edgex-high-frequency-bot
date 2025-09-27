#!/bin/bash
echo "=== Docker構建診斷腳本 ==="
echo "開始時間: $(date)"

# 步驟1：檢查Docker服務狀態
echo "1. 檢查Docker服務狀態..."
docker version
if [ $? -ne 0 ]; then
    echo "錯誤: Docker服務未運行"
    exit 1
fi

# 步驟2：測試基礎鏡像下載（使用平台指定避免IPv6問題）
echo "2. 測試基礎鏡像下載..."
echo "下載Rust基礎鏡像..."
docker pull --platform linux/amd64 rust:1.75
if [ $? -eq 0 ]; then
    echo "✓ Rust鏡像下載成功"
else
    echo "✗ Rust鏡像下載失敗，嘗試使用國內鏡像源"
    docker pull --platform linux/amd64 registry.cn-hangzhou.aliyuncs.com/library/rust:1.75
fi

echo "下載Alpine基礎鏡像..."
docker pull --platform linux/amd64 alpine:latest
if [ $? -eq 0 ]; then
    echo "✓ Alpine鏡像下載成功"
else
    echo "✗ Alpine鏡像下載失敗，嘗試使用國內鏡像源"
    docker pull --platform linux/amd64 registry.cn-hangzhou.aliyuncs.com/library/alpine:latest
fi

# 步驟3：測試本地Rust構建
echo "3. 測試本地Rust構建..."
cargo build --release
if [ $? -eq 0 ]; then
    echo "✓ 本地Rust構建成功"
else
    echo "✗ 本地Rust構建失敗，檢查Cargo.toml配置"
    exit 1
fi

# 步驟4：分步Docker構建
echo "4. 開始Docker構建..."
docker build --platform linux/amd64 -t edgex-high-frequency-bot .
if [ $? -eq 0 ]; then
    echo "✓ Docker構建成功"
    
    # 步驟5：驗證鏡像
    echo "5. 驗證構建的鏡像..."
    docker images | grep edgex-high-frequency-bot
    echo "鏡像大小: $(docker images edgex-high-frequency-bot --format "table {{.Size}}")"
else
    echo "✗ Docker構建失敗"
    echo "嘗試使用無緩存構建..."
    docker build --no-cache --platform linux/amd64 -t edgex-high-frequency-bot .
fi

echo "=== 構建診斷完成 ==="
echo "完成時間: $(date)"
