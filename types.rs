use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub api_key: String,
    pub secret_key: String,
    pub initial_balance: f64,
    pub target_volatility: f64,
    pub base_position_size: f64,
    pub max_trades_per_day: u32,
    pub min_trade_interval: u64,
    pub max_trade_interval: u64,
    pub stop_loss_pct: f64,
    pub take_profit_pct: f64,
    pub symbols: Vec<String>,
    pub timeframe: String,
}

#[derive(Debug, Clone)]
pub struct PriceData {
    pub timestamp: i64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

#[derive(Debug, Clone)]
pub struct TradeSignal {
    pub symbol: String,
    pub direction: TradeDirection,
    pub confidence: f64,
    pub price: f64,
    pub stop_loss: f64,
    pub take_profit: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum TradeDirection {
    Long,
    Short,
    Hold,
}

#[derive(Debug, Clone)]
pub struct Position {
    pub symbol: String,
    pub direction: TradeDirection,
    pub size: f64,
    pub entry_price: f64,
    pub stop_loss: f64,
    pub take_profit: f64,
    pub leverage: u32,
    pub opening_time: i64,
}

#[derive(Debug, Clone)]
pub struct AccountInfo {
    pub balance: f64,
    pub available_balance: f64,
    pub positions: HashMap<String, Position>,
}

#[derive(Debug, Clone)]
pub struct Order {
    pub symbol: String,
    pub side: OrderSide,
    pub order_type: OrderType,
    pub quantity: f64,
    pub price: Option<f64>,
    pub leverage: u32,
}

#[derive(Debug, Clone, PartialEq)]
pub enum OrderSide {
    Buy,
    Sell,
}

#[derive(Debug, Clone, PartialEq)]
pub enum OrderType {
    Market,
    Limit,
}

#[derive(Debug, Clone)]
pub struct TradeRecord {
    pub symbol: String,
    pub direction: TradeDirection,
    pub size: f64,
    pub entry_price: f64,
    pub exit_price: f64,
    pub pnl: f64,
    pub timestamp: i64,
    pub duration: u64,
}
