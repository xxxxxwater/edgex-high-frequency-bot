use crate::types::*;
use chrono::{DateTime, Utc};
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};

pub struct PerformanceMonitor {
    strategy: Arc<Mutex<HighFrequencyStrategy>>,
}

impl PerformanceMonitor {
    pub fn new(strategy: Arc<Mutex<HighFrequencyStrategy>>) -> Self {
        Self { strategy }
    }

    pub async fn start_monitoring(self) {
        tokio::spawn(async move {
            loop {
                if let Ok(report) = self.generate_performance_report().await {
                    self.print_report(&report);
                }
                
                // 每小时报告一次
                sleep(Duration::from_secs(3600)).await;
            }
        });
    }

    async fn generate_performance_report(&self) -> anyhow::Result<PerformanceReport> {
        let strategy = self.strategy.lock().await;
        
        let current_volatility = strategy.get_current_volatility();
        let daily_volume = strategy.calculate_daily_volume();
        let volume_target = strategy.balance * 100.0;
        let volume_ratio = daily_volume / volume_target;
        
        let today_pnl = strategy.trade_records.iter()
            .filter(|record| {
                let trade_time = DateTime::from_timestamp(record.timestamp, 0).unwrap();
                let now = Utc::now();
                (now - trade_time).num_hours() < 24
            })
            .map(|record| record.pnl)
            .sum();
        
        Ok(PerformanceReport {
            timestamp: Utc::now(),
            portfolio_value: strategy.balance,
            current_volatility,
            target_volatility: strategy.config.target_volatility,
            volatility_ratio: current_volatility / strategy.config.target_volatility,
            daily_volume,
            volume_target,
            volume_ratio,
            today_trades: strategy.trade_count,
            today_pnl,
            trading_interval: strategy.trading_interval,
        })
    }

    fn print_report(&self, report: &PerformanceReport) {
        println!("\n{}", "=".repeat(60));
        println!("高频策略性能报告");
        println!("{}", "=".repeat(60));
        println!("时间: {}", report.timestamp.format("%Y-%m-%d %H:%M:%S"));
        println!("净值: {:.2} USDT", report.portfolio_value);
        println!("今日盈亏: {:.4} USDT", report.today_pnl);
        println!("波动率: {:.4} (目标: {:.4})", report.current_volatility, report.target_volatility);
        println!("波动率比率: {:.2}", report.volatility_ratio);
        println!("交易量: {:.2} / {:.2} ({:.2}%)", report.daily_volume, report.volume_target, report.volume_ratio * 100.0);
        println!("交易次数: {}", report.today_trades);
        println!("交易间隔: {}秒", report.trading_interval);
        println!("{}", "=".repeat(60));
    }
}

#[derive(Debug)]
pub struct PerformanceReport {
    pub timestamp: DateTime<Utc>,
    pub portfolio_value: f64,
    pub current_volatility: f64,
    pub target_volatility: f64,
    pub volatility_ratio: f64,
    pub daily_volume: f64,
    pub volume_target: f64,
    pub volume_ratio: f64,
    pub today_trades: u32,
    pub today_pnl: f64,
    pub trading_interval: u64,
}