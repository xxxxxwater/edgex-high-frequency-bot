use crate::types::*;
use crate::edgex_client::EdgeXClient;
use anyhow::Result;
use chrono::{DateTime, Utc};
use std::collections::VecDeque;
use tokio::time::{sleep, Duration, Instant};

pub struct HighFrequencyStrategy {
    client: EdgeXClient,
    config: Config,
    balance: f64,
    equity_history: VecDeque<f64>,
    trade_count: u32,
    trading_interval: u64,
    positions: std::collections::HashMap<String, Position>,
    trade_records: Vec<TradeRecord>,
    websocket_client: Option<EdgeXWebSocketClient>,
    kline_manager: KlineManager,
    use_websocket: bool,
}

impl HighFrequencyStrategy {
    pub fn new(client: EdgeXClient, config: Config) -> Self {
        let initial_balance = config.initial_balance;
        let mut equity_history = VecDeque::new();
        equity_history.push_back(initial_balance);
        
        Self {
            client,
            config,
            balance: initial_balance,
            equity_history,
            trade_count: 0,
            trading_interval: config.min_trade_interval,
            positions: std::collections::HashMap::new(),
            trade_records: Vec::new(),
        }
    }

    pub async fn run(&mut self) -> Result<()> {
        log::info!("启动高频低波动策略");
        
        // 主循环
        loop {
            // 更新账户信息
            if let Ok(account_info) = self.client.get_account_info().await {
                self.balance = account_info.balance;
                self.equity_history.push_back(self.balance);
                if self.equity_history.len() > 100 {
                    self.equity_history.pop_front();
                }
            }

            // 检查波动率限制
            if self.check_volatility_limits() {
                log::warn!("波动率超标，暂停交易5分钟");
                sleep(Duration::from_secs(300)).await;
                continue;
            }

            // 检查每日交易限制
            if self.trade_count >= self.config.max_trades_per_day {
                log::info!("达到每日交易次数限制，暂停交易1小时");
                sleep(Duration::from_secs(3600)).await;
                continue;
            }

            // 执行交易
            for symbol in &self.config.symbols {
                if let Err(e) = self.execute_trade(symbol).await {
                    log::error!("交易执行错误: {}", e);
                }
            }

            // 检查交易量目标
            self.check_volume_target();

            // 等待下一次交易机会
            sleep(Duration::from_secs(self.trading_interval)).await;
        }
    }

    async fn execute_trade(&mut self, symbol: &str) -> Result<()> {
        // 获取价格数据
        let klines = self.client.get_klines(symbol, &self.config.timeframe, 30).await?;
        
        if klines.is_empty() {
            return Ok(());
        }

        // 生成交易信号
        let signal = self.generate_signal(symbol, &klines);
        
        if signal.direction == TradeDirection::Hold {
            return Ok(());
        }

        // 计算当前价格和波动率
        let current_price = klines.last().unwrap().close;
        let volatility = self.calculate_volatility(&klines);

        // 计算仓位大小
        let position_size = self.calculate_position_size(current_price, volatility);

        // 执行交易
        let order = Order {
            symbol: symbol.to_string(),
            side: match signal.direction {
                TradeDirection::Long => OrderSide::Buy,
                TradeDirection::Short => OrderSide::Sell,
                TradeDirection::Hold => return Ok(()),
            },
            order_type: OrderType::Market,
            quantity: position_size,
            price: None,
            leverage: 50, // 使用50倍杠杆
        };

        if let Ok(result) = self.client.place_order(&order).await {
            log::info!("开仓: {} {} {} @ {}", 
                match signal.direction {
                    TradeDirection::Long => "做多",
                    TradeDirection::Short => "做空",
                    TradeDirection::Hold => "持有",
                }, 
                position_size, symbol, current_price
            );

            // 记录仓位
            let position = Position {
                symbol: symbol.to_string(),
                direction: signal.direction.clone(),
                size: position_size,
                entry_price: current_price,
                stop_loss: signal.stop_loss,
                take_profit: signal.take_profit,
                leverage: 50,
                opening_time: Utc::now().timestamp(),
            };
            
            self.positions.insert(symbol.to_string(), position);
            self.trade_count += 1;

            // 短暂持有后平仓
            sleep(Duration::from_secs(3)).await;
            
            if let Err(e) = self.close_position(symbol).await {
                log::error!("平仓错误: {}", e);
            }

            // 调整交易频率
            self.adjust_trading_frequency();
        }

        Ok(())
    }

    async fn close_position(&mut self, symbol: &str) -> Result<()> {
        if let Some(position) = self.positions.get(symbol) {
            // 获取当前价格
            let klines = self.client.get_klines(symbol, "1m", 1).await?;
            if klines.is_empty() {
                return Ok(());
            }
            
            let current_price = klines[0].close;
            
            // 创建平仓订单
            let close_order = Order {
                symbol: symbol.to_string(),
                side: match position.direction {
                    TradeDirection::Long => OrderSide::Sell,
                    TradeDirection::Short => OrderSide::Buy,
                    TradeDirection::Hold => OrderSide::Buy, // 不应该发生
                },
                order_type: OrderType::Market,
                quantity: position.size,
                price: None,
                leverage: position.leverage,
            };

            if let Ok(result) = self.client.place_order(&close_order).await {
                // 计算盈亏
                let pnl = match position.direction {
                    TradeDirection::Long => (current_price - position.entry_price) * position.size,
                    TradeDirection::Short => (position.entry_price - current_price) * position.size,
                    TradeDirection::Hold => 0.0,
                };

                // 记录交易
                let trade_record = TradeRecord {
                    symbol: symbol.to_string(),
                    direction: position.direction.clone(),
                    size: position.size,
                    entry_price: position.entry_price,
                    exit_price: current_price,
                    pnl,
                    timestamp: Utc::now().timestamp(),
                    duration: (Utc::now().timestamp() - position.opening_time) as u64,
                };
                
                self.trade_records.push(trade_record);
                
                log::info!("平仓: {} {} @ {}, 盈亏: {:.4} USDT", 
                    symbol, position.size, current_price, pnl
                );

                // 移除仓位记录
                self.positions.remove(symbol);
            }
        }
        
        Ok(())
    }

    fn generate_signal(&self, symbol: &str, price_data: &[PriceData]) -> TradeSignal {
        if price_data.len() < 20 {
            return TradeSignal {
                symbol: symbol.to_string(),
                direction: TradeDirection::Hold,
                confidence: 0.0,
                price: 0.0,
                stop_loss: 0.0,
                take_profit: 0.0,
            };
        }

        // 计算移动平均线
        let short_ma = self.calculate_moving_average(price_data, 5);
        let medium_ma = self.calculate_moving_average(price_data, 20);

        let current_price = price_data.last().unwrap().close;
        let price_deviation = (current_price - medium_ma) / medium_ma;

        let (direction, stop_loss, take_profit) = if price_deviation > 0.002 {
            // 价格偏离0.2%以上，做空
            (
                TradeDirection::Short,
                current_price * (1.0 + self.config.stop_loss_pct),
                current_price * (1.0 - self.config.take_profit_pct),
            )
        } else if price_deviation < -0.002 {
            // 价格偏离-0.2%以下，做多
            (
                TradeDirection::Long,
                current_price * (1.0 - self.config.stop_loss_pct),
                current_price * (1.0 + self.config.take_profit_pct),
            )
        } else {
            return TradeSignal {
                symbol: symbol.to_string(),
                direction: TradeDirection::Hold,
                confidence: 0.0,
                price: current_price,
                stop_loss: 0.0,
                take_profit: 0.0,
            };
        };

        let confidence = price_deviation.abs();

        TradeSignal {
            symbol: symbol.to_string(),
            direction,
            confidence,
            price: current_price,
            stop_loss,
            take_profit,
        }
    }

    fn calculate_moving_average(&self, price_data: &[PriceData], period: usize) -> f64 {
        if price_data.len() < period {
            return 0.0;
        }
        
        let sum: f64 = price_data.iter()
            .rev()
            .take(period)
            .map(|p| p.close)
            .sum();
            
        sum / period as f64
    }

    fn calculate_volatility(&self, price_data: &[PriceData]) -> f64 {
        if price_data.len() < 2 {
            return 0.01; // 默认值
        }

        let returns: Vec<f64> = price_data.windows(2)
            .map(|window| (window[1].close - window[0].close) / window[0].close)
            .collect();

        if returns.is_empty() {
            return 0.01;
        }

        let mean = returns.iter().sum::<f64>() / returns.len() as f64;
        let variance = returns.iter()
            .map(|r| (r - mean).powi(2))
            .sum::<f64>() / returns.len() as f64;
        
        (variance.sqrt() * (252.0_f64).sqrt()).max(0.01)
    }

    fn calculate_position_size(&self, current_price: f64, volatility: f64) -> f64 {
        // 基础仓位大小 (0.1%的账户余额)
        let base_size = self.balance * self.config.base_position_size / current_price;
        
        // 根据波动率调整仓位
        let volatility_adjustment = if volatility > 0.0 {
            (0.002 / volatility).min(1.0)
        } else {
            1.0
        };
        
        base_size * volatility_adjustment
    }

    fn check_volatility_limits(&self) -> bool {
        if self.equity_history.len() < 20 {
            return false;
        }
        
        let returns: Vec<f64> = self.equity_history.iter()
            .zip(self.equity_history.iter().skip(1))
            .map(|(&a, &b)| (b - a) / a)
            .collect();

        if returns.len() < 2 {
            return false;
        }

        let volatility = self.calculate_standard_deviation(&returns) * (252.0_f64).sqrt();
        
        // 如果波动率超过目标，返回true
        volatility > self.config.target_volatility * 1.2
    }

    fn calculate_standard_deviation(&self, data: &[f64]) -> f64 {
        let mean = data.iter().sum::<f64>() / data.len() as f64;
        let variance = data.iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>() / data.len() as f64;
        
        variance.sqrt()
    }

    fn check_volume_target(&self) {
        let daily_volume = self.calculate_daily_volume();
        let volume_target = self.balance * 100.0;
        let volume_ratio = daily_volume / volume_target;

        log::info!("交易量进度: {:.2}/{:.2} ({:.2}%)", 
            daily_volume, volume_target, volume_ratio * 100.0
        );

        // 如果交易量不足，增加交易频率
        if volume_ratio < 0.8 && self.trade_count < self.config.max_trades_per_day {
            self.increase_trading_frequency();
        }
    }

    fn calculate_daily_volume(&self) -> f64 {
        // 计算当日交易量 (简单估算)
        self.trade_records.iter()
            .filter(|record| {
                let trade_time = DateTime::from_timestamp(record.timestamp, 0).unwrap();
                let now = Utc::now();
                (now - trade_time).num_hours() < 24
            })
            .map(|record| record.size * record.entry_price * 2.0) // 买卖双方
            .sum()
    }

    fn adjust_trading_frequency(&mut self) {
        let volume_ratio = self.calculate_daily_volume() / (self.balance * 100.0);
        let current_volatility = self.get_current_volatility();
        let volatility_ratio = current_volatility / self.config.target_volatility;

        // 基于交易量和波动率调整频率
        if volume_ratio < 0.8 && volatility_ratio < 0.8 {
            self.increase_trading_frequency();
        } else if volatility_ratio > 1.2 {
            self.reduce_trading_frequency();
        }
    }

    fn get_current_volatility(&self) -> f64 {
        if self.equity_history.len() < 20 {
            return 0.0;
        }
        
        let returns: Vec<f64> = self.equity_history.iter()
            .zip(self.equity_history.iter().skip(1))
            .map(|(&a, &b)| (b - a) / a)
            .collect();

        if returns.len() < 2 {
            return 0.0;
        }

        self.calculate_standard_deviation(&returns) * (252.0_f64).sqrt()
    }

    fn increase_trading_frequency(&mut self) {
        // 只有在波动率低于目标时才增加频率
        if self.get_current_volatility() < self.config.target_volatility * 0.8 {
            self.trading_interval = (self.config.min_trade_interval as f64 * 0.9)
                .max(self.config.min_trade_interval as f64) as u64;
            
            log::info!("增加交易频率: 间隔{}秒", self.trading_interval);
        }
    }

    fn reduce_trading_frequency(&mut self) {
        self.trading_interval = (self.trading_interval as f64 * 1.5)
            .min(self.config.max_trade_interval as f64) as u64;
        
        log::info!("降低交易频率: 间隔{}秒", self.trading_interval);
    }
}



