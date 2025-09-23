mod types;
mod edgex_client;
mod strategy;
mod monitor;

use crate::edgex_client::EdgeXClient;
use crate::strategy::HighFrequencyStrategy;
use crate::monitor::PerformanceMonitor;
use crate::types::Config;
use anyhow::Result;
use std::sync::Arc;
use tokio::sync::Mutex;

#[tokio::main]
async fn main() -> Result<()> {
    // 初始化日志
    env_logger::init();
    
    // 配置参数
    let config = Config {
        api_key: std::env::var("EDGEX_API_KEY").expect("EDGEX_API_KEY must be set"),
        secret_key: std::env::var("EDGEX_SECRET_KEY").expect("EDGEX_SECRET_KEY must be set"),
        initial_balance: 10000.0,
        target_volatility: 0.005,      // 0.5%波动率目标
        base_position_size: 0.001,     // 基础仓位比例0.1%
        max_trades_per_day: 200,       // 每日最大交易次数
        min_trade_interval: 5,         // 最小交易间隔5秒
        max_trade_interval: 60,        // 最大交易间隔60秒
        stop_loss_pct: 0.002,          // 止损0.2%
        take_profit_pct: 0.002,        // 止盈0.2%
        symbols: vec!["BTCUSDT".to_string()],
        timeframe: "1m".to_string(),
    };

    // 创建EdgeX客户端
    let client = EdgeXClient::new(
        config.api_key.clone(),
        config.secret_key.clone(),
        false, // 生产环境
    );

    // 创建策略实例
    let strategy = HighFrequencyStrategy::new(client, config);
    let strategy = Arc::new(Mutex::new(strategy));

    // 启动性能监控
    let monitor = PerformanceMonitor::new(Arc::clone(&strategy));
    monitor.start_monitoring().await;

    // 运行策略
    let strategy_clone = Arc::clone(&strategy);
    tokio::spawn(async move {
        let mut strategy = strategy_clone.lock().await;
        if let Err(e) = strategy.run().await {
            log::error!("策略运行错误: {}", e);
        }
    });

    // 等待Ctrl+C信号
    tokio::signal::ctrl_c().await?;
    log::info!("收到停止信号，退出程序");

    Ok(())
}