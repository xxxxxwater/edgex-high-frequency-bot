#!/bin/bash
set -e

echo "========================================"
echo "EdgeX 高频交易机器人启动"
echo "========================================"
echo ""

# 配置文件路径
CONFIG_FILE="${CONFIG_FILE:-/app/.env}"
CONFIG_TEMPLATE="/app/config.template"

# 检查是否需要创建配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️  未找到配置文件: $CONFIG_FILE"
    
    # 检查是否有环境变量配置
    if [ -z "$EDGEX_ACCOUNT_ID" ]; then
        echo ""
        echo "❌ 错误: 未找到配置！"
        echo ""
        echo "请使用以下方式之一提供配置："
        echo ""
        echo "方式1: 挂载配置文件"
        echo "  docker run -v /path/to/.env:/app/.env ..."
        echo ""
        echo "方式2: 设置环境变量"
        echo "  docker run -e EDGEX_ACCOUNT_ID=xxx -e EDGEX_STARK_PRIVATE_KEY=yyy ..."
        echo ""
        echo "方式3: 使用 docker-compose"
        echo "  参考 docker-compose.yml 配置"
        echo ""
        exit 1
    else
        echo "✅ 从环境变量加载配置"
        
        # 从环境变量生成配置文件
        cat > "$CONFIG_FILE" << EOF
# EdgeX 交易机器人配置（自动生成）
EDGEX_ACCOUNT_ID=${EDGEX_ACCOUNT_ID}
EDGEX_STARK_PRIVATE_KEY=${EDGEX_STARK_PRIVATE_KEY}
EDGEX_PUBLIC_KEY=${EDGEX_PUBLIC_KEY}
EDGEX_PUBLIC_KEY_Y_COORDINATE=${EDGEX_PUBLIC_KEY_Y_COORDINATE}
EDGEX_API_KEY=${EDGEX_API_KEY:-}
EDGEX_SECRET_KEY=${EDGEX_SECRET_KEY:-}
EDGEX_TESTNET=${EDGEX_TESTNET:-false}
EDGEX_SYMBOLS=${EDGEX_SYMBOLS:-BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT}
EDGEX_BASE_POSITION_SIZE=${EDGEX_BASE_POSITION_SIZE:-0.05}
EDGEX_LEVERAGE=${EDGEX_LEVERAGE:-50}
EDGEX_TAKE_PROFIT_PCT=${EDGEX_TAKE_PROFIT_PCT:-0.004}
EDGEX_STOP_LOSS_PCT=${EDGEX_STOP_LOSS_PCT:-0.004}
EDGEX_TARGET_VOLATILITY=${EDGEX_TARGET_VOLATILITY:-0.60}
EDGEX_MIN_ORDER_SIZE=${EDGEX_MIN_ORDER_SIZE:-0.3}
EDGEX_MAX_POSITION_PCT=${EDGEX_MAX_POSITION_PCT:-0.5}
EDGEX_MIN_TRADE_INTERVAL=${EDGEX_MIN_TRADE_INTERVAL:-5000}
EDGEX_MAX_TRADE_INTERVAL=${EDGEX_MAX_TRADE_INTERVAL:-60000}
EDGEX_PERFORMANCE_REPORT_INTERVAL=${EDGEX_PERFORMANCE_REPORT_INTERVAL:-300}
EDGEX_LOG_LEVEL=${EDGEX_LOG_LEVEL:-INFO}
EOF
        echo "✅ 配置文件已创建: $CONFIG_FILE"
    fi
else
    echo "✅ 找到配置文件: $CONFIG_FILE"
fi

# 创建必要的目录
mkdir -p /app/logs /app/data

echo ""
echo "配置信息："
echo "----------------------------------------"
if [ -f "$CONFIG_FILE" ]; then
    # 显示配置（隐藏敏感信息）
    grep "^EDGEX_ACCOUNT_ID=" "$CONFIG_FILE" | sed 's/=.*/=***/' || true
    grep "^EDGEX_TESTNET=" "$CONFIG_FILE" || true
    grep "^EDGEX_SYMBOLS=" "$CONFIG_FILE" || true
    grep "^EDGEX_LEVERAGE=" "$CONFIG_FILE" || true
fi
echo "----------------------------------------"
echo ""

# 执行传入的命令，默认启动主程序
if [ $# -eq 0 ]; then
    echo "🚀 启动交易机器人..."
    echo ""
    exec python main.py
else
    exec "$@"
fi

