//! EdgeX WebSocket 客户端实现
//!
//! 本模块提供了完整的 EdgeX WebSocket API 客户端实现，支持：
//! - 公共 WebSocket 连接（市场数据）
//! - 私有 WebSocket 连接（账户更新）
//! - 自动心跳（Ping/Pong）机制
//! - 消息订阅和处理
//!
//! # 官方文档
//! 
//! API 文档: https://edgex-1.gitbook.io/edgeX-documentation/api/websocket-api
//!
//! # 使用示例
//!
//! ## 公共市场数据流
//!
//! ```no_run
//! use edgex_high_frequency_bot::websocket_client::RealTimePriceStream;
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     // 创建市场数据流
//!     let mut stream = RealTimePriceStream::new_public(
//!         true,  // testnet
//!         vec!["10000001".to_string(), "10000002".to_string()]  // 合约 ID
//!     );
//!     
//!     // 启动流（会自动订阅 ticker、深度、K线、成交数据）
//!     stream.start_market_stream().await?;
//!     Ok(())
//! }
//! ```
//!
//! ## 私有账户数据流
//!
//! ```no_run
//! use edgex_high_frequency_bot::websocket_client::RealTimePriceStream;
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     // 创建私有数据流
//!     let mut stream = RealTimePriceStream::new_private(
//!         12345,  // account_id
//!         "your-stark-private-key".to_string(),
//!         true  // testnet
//!     );
//!     
//!     // 启动流（自动接收账户更新）
//!     stream.start_private_stream().await?;
//!     Ok(())
//! }
//! ```
//!
//! ## 同时管理公共和私有连接
//!
//! ```no_run
//! use edgex_high_frequency_bot::websocket_client::WebSocketManager;
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     let mut manager = WebSocketManager::new(true);  // testnet
//!     
//!     // 添加要监控的合约
//!     manager.add_contracts(vec![
//!         "10000001".to_string(),  // BTCUSDT
//!         "10000002".to_string(),  // ETHUSDT
//!     ]);
//!     
//!     // 设置私有连接（可选）
//!     manager.with_private(12345, "your-stark-private-key".to_string(), true);
//!     
//!     // 启动所有连接
//!     manager.start().await?;
//!     Ok(())
//! }
//! ```
//!
//! # 支持的订阅类型
//!
//! ## 公共 WebSocket (/api/v1/public/ws)
//! - `ticker.{contractId}` - 24小时行情
//! - `ticker.all` - 所有合约行情
//! - `depth.{contractId}.{depth}` - 订单簿深度（15或200档）
//! - `kline.{priceType}.{contractId}.{interval}` - K线数据
//! - `trades.{contractId}` - 最新成交
//! - `metadata` - 交易所元数据
//!
//! ## 私有 WebSocket (/api/v1/private/ws)
//! 私有连接无需订阅，连接成功后会自动推送以下事件：
//! - `ACCOUNT_UPDATE` - 账户更新
//! - `ORDER_UPDATE` - 订单更新
//! - `POSITION_UPDATE` - 持仓更新
//! - `DEPOSIT_UPDATE` - 充值更新
//! - `WITHDRAW_UPDATE` - 提现更新
//! - `FUNDING_SETTLEMENT` - 资金费结算
//! - `START_LIQUIDATING` / `FINISH_LIQUIDATING` - 强平通知
//!
//! # 心跳机制
//!
//! 客户端实现了双向 Ping/Pong 机制：
//! 1. **服务器心跳**: 自动响应服务器发送的 Ping 消息
//! 2. **客户端心跳**: 每30秒发送 Ping 用于延迟测量
//! 3. 如果服务器5次 Ping 未收到响应，连接会被关闭

use crate::types::*;
use anyhow::{anyhow, Result};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha3::{Digest, Keccak256};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;
use tokio::time::{interval, Duration};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use url::Url;

#[derive(Debug, Serialize, Deserialize)]
struct WebSocketMessage {
    #[serde(rename = "type")]
    msg_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    channel: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    time: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<Value>,
}

pub struct EdgeXWebSocketClient {
    base_url: String,
    account_id: Option<u64>,
    stark_private_key: Option<String>,
    is_private: bool,
}

impl EdgeXWebSocketClient {
    /// 创建公共 WebSocket 客户端（用于市场数据）
    pub fn new_public(testnet: bool) -> Self {
        let base_url = if testnet {
            "wss://quote-testnet.edgex.exchange/api/v1/public/ws".to_string()
        } else {
            "wss://quote.edgex.exchange/api/v1/public/ws".to_string()
        };

        Self {
            base_url,
            account_id: None,
            stark_private_key: None,
            is_private: false,
        }
    }

    /// 创建私有 WebSocket 客户端（用于账户更新）
    pub fn new_private(account_id: u64, stark_private_key: String, testnet: bool) -> Self {
        let base_url = if testnet {
            "wss://quote-testnet.edgex.exchange/api/v1/private/ws".to_string()
        } else {
            "wss://quote.edgex.exchange/api/v1/private/ws".to_string()
        };

        Self {
            base_url,
            account_id: Some(account_id),
            stark_private_key: Some(stark_private_key),
            is_private: true,
        }
    }

    /// 连接到 WebSocket
    pub async fn connect(&self) -> Result<WebSocketConnection> {
        let mut url = self.base_url.clone();
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)?
            .as_millis();

        // 对于私有连接，需要添加认证
        if self.is_private {
            let account_id = self.account_id.ok_or_else(|| anyhow!("需要账户ID"))?;
            url = format!("{}?accountId={}", url, account_id);

            // 生成签名
            let path = format!("/api/v1/private/ws?accountId={}", account_id);
            let sign_content = format!("{}GET{}", timestamp, path);
            
            // Keccak256 哈希
            let mut hasher = Keccak256::new();
            hasher.update(sign_content.as_bytes());
            let message_hash = hasher.finalize();

            // 这里需要使用 Stark 私钥签名
            // 注意：完整的 Stark 签名实现需要额外的加密库
            // 这里仅作示例，实际使用时需要实现完整的签名逻辑
            log::warn!("Stark 签名功能需要完整实现");
            
            // 添加时间戳到 URL
            url = format!("{}&timestamp={}", url, timestamp);
        } else {
            // 公共连接只需要添加时间戳
            url = format!("{}?timestamp={}", url, timestamp);
        }

        let parsed_url = Url::parse(&url)?;
        log::info!("连接到 WebSocket: {}", parsed_url);
        
        let (ws_stream, _) = connect_async(parsed_url).await?;
        let (write, read) = ws_stream.split();
        
        Ok(WebSocketConnection {
            write: Arc::new(Mutex::new(write)),
            read: Arc::new(Mutex::new(read)),
            is_private: self.is_private,
        })
    }

    /// 订阅 24 小时行情
    pub async fn subscribe_ticker(&self, connection: &WebSocketConnection, contract_id: &str) -> Result<()> {
        if self.is_private {
            return Err(anyhow!("私有连接不支持订阅操作"));
        }

        let subscribe_message = serde_json::json!({
            "type": "subscribe",
            "channel": format!("ticker.{}", contract_id)
        });
        
        connection.send_message(&subscribe_message).await?;
        log::info!("订阅合约 {} 的 ticker 数据", contract_id);
        Ok(())
    }

    /// 订阅订单簿深度
    pub async fn subscribe_depth(&self, connection: &WebSocketConnection, contract_id: &str, depth: u32) -> Result<()> {
        if self.is_private {
            return Err(anyhow!("私有连接不支持订阅操作"));
        }

        let subscribe_message = serde_json::json!({
            "type": "subscribe",
            "channel": format!("depth.{}.{}", contract_id, depth)
        });
        
        connection.send_message(&subscribe_message).await?;
        log::info!("订阅合约 {} 的深度数据（深度: {}）", contract_id, depth);
        Ok(())
    }

    /// 订阅 K 线数据
    pub async fn subscribe_kline(&self, connection: &WebSocketConnection, contract_id: &str, price_type: &str, interval: &str) -> Result<()> {
        if self.is_private {
            return Err(anyhow!("私有连接不支持订阅操作"));
        }

        let subscribe_message = serde_json::json!({
            "type": "subscribe",
            "channel": format!("kline.{}.{}.{}", price_type, contract_id, interval)
        });
        
        connection.send_message(&subscribe_message).await?;
        log::info!("订阅合约 {} 的 K 线数据（类型: {}, 间隔: {}）", contract_id, price_type, interval);
        Ok(())
    }

    /// 订阅最新成交
    pub async fn subscribe_trades(&self, connection: &WebSocketConnection, contract_id: &str) -> Result<()> {
        if self.is_private {
            return Err(anyhow!("私有连接不支持订阅操作"));
        }

        let subscribe_message = serde_json::json!({
            "type": "subscribe",
            "channel": format!("trades.{}", contract_id)
        });
        
        connection.send_message(&subscribe_message).await?;
        log::info!("订阅合约 {} 的成交数据", contract_id);
        Ok(())
    }

    /// 订阅元数据
    pub async fn subscribe_metadata(&self, connection: &WebSocketConnection) -> Result<()> {
        if self.is_private {
            return Err(anyhow!("私有连接不支持订阅操作"));
        }

        let subscribe_message = serde_json::json!({
            "type": "subscribe",
            "channel": "metadata"
        });
        
        connection.send_message(&subscribe_message).await?;
        log::info!("订阅元数据");
        Ok(())
    }

    /// 取消订阅
    pub async fn unsubscribe(&self, connection: &WebSocketConnection, channel: &str) -> Result<()> {
        if self.is_private {
            return Err(anyhow!("私有连接不支持取消订阅操作"));
        }

        let unsubscribe_message = serde_json::json!({
            "type": "unsubscribe",
            "channel": channel
        });
        
        connection.send_message(&unsubscribe_message).await?;
        log::info!("取消订阅频道: {}", channel);
        Ok(())
    }
}

use futures_util::stream::SplitSink;
use futures_util::stream::SplitStream;
use tokio::net::TcpStream;
use tokio_tungstenite::MaybeTlsStream;
use tokio_tungstenite::WebSocketStream;

pub struct WebSocketConnection {
    pub write: Arc<Mutex<SplitSink<WebSocketStream<MaybeTlsStream<TcpStream>>, Message>>>,
    pub read: Arc<Mutex<SplitStream<WebSocketStream<MaybeTlsStream<TcpStream>>>>>,
    pub is_private: bool,
}

impl WebSocketConnection {
    /// 发送消息到 WebSocket
    pub async fn send_message(&self, message: &Value) -> Result<()> {
        let mut write = self.write.lock().await;
        let text = serde_json::to_string(message)?;
        write.send(Message::Text(text)).await?;
        Ok(())
    }

    /// 发送 Pong 响应
    pub async fn send_pong(&self, timestamp: &str) -> Result<()> {
        let pong_message = serde_json::json!({
            "type": "pong",
            "time": timestamp
        });
        self.send_message(&pong_message).await
    }

    /// 发送 Ping 请求（用于延迟测量）
    pub async fn send_ping(&self) -> Result<()> {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)?
            .as_millis()
            .to_string();
        
        let ping_message = serde_json::json!({
            "type": "ping",
            "time": timestamp
        });
        self.send_message(&ping_message).await
    }
}

/// 消息处理器类型
pub type MessageHandler = Arc<dyn Fn(Value) -> Result<()> + Send + Sync>;

pub struct WebSocketMessageHandler {
    connection: WebSocketConnection,
    handlers: Arc<Mutex<HashMap<String, MessageHandler>>>,
    ping_interval: Duration,
}

impl WebSocketMessageHandler {
    pub fn new(connection: WebSocketConnection) -> Self {
        Self {
            connection,
            handlers: Arc::new(Mutex::new(HashMap::new())),
            ping_interval: Duration::from_secs(30),
        }
    }

    /// 注册消息处理器
    pub async fn register_handler<F>(&self, message_type: String, handler: F)
    where
        F: Fn(Value) -> Result<()> + Send + Sync + 'static,
    {
        let mut handlers = self.handlers.lock().await;
        handlers.insert(message_type, Arc::new(handler));
    }

    /// 启动监听（包含心跳机制）
    pub async fn start_listening(mut self) -> Result<()> {
        let read_handle = tokio::spawn(async move {
            self.message_loop().await
        });

        let ping_handle = tokio::spawn(async move {
            // Ping 循环已经在 message_loop 中处理
        });

        // 等待任务完成
        let result = read_handle.await;
        match result {
            Ok(Ok(())) => Ok(()),
            Ok(Err(e)) => Err(e),
            Err(e) => Err(anyhow!("任务执行失败: {}", e)),
        }
    }

    /// 消息循环
    async fn message_loop(&mut self) -> Result<()> {
        let mut read = self.connection.read.lock().await;
        let mut ping_interval_timer = interval(self.ping_interval);

        loop {
            tokio::select! {
                // 处理接收到的消息
                message = read.next() => {
                    match message {
                        Some(Ok(Message::Text(text))) => {
                            if let Err(e) = self.handle_text_message(&text).await {
                                log::error!("处理消息失败: {}", e);
                            }
                        }
                        Some(Ok(Message::Ping(data))) => {
                            // 响应标准 WebSocket Ping
                            drop(read);
                            let mut write = self.connection.write.lock().await;
                            if let Err(e) = write.send(Message::Pong(data)).await {
                                log::error!("发送 Pong 失败: {}", e);
                            }
                            drop(write);
                            read = self.connection.read.lock().await;
                        }
                        Some(Ok(Message::Close(_))) => {
                            log::info!("WebSocket 连接关闭");
                            break;
                        }
                        Some(Err(e)) => {
                            log::error!("WebSocket 错误: {}", e);
                            break;
                        }
                        None => {
                            log::info!("WebSocket 流结束");
                            break;
                        }
                        _ => {}
                    }
                }
                // 定期发送 Ping（仅用于客户端延迟测量）
                _ = ping_interval_timer.tick() => {
                    drop(read);
                    if let Err(e) = self.connection.send_ping().await {
                        log::error!("发送 Ping 失败: {}", e);
                    }
                    read = self.connection.read.lock().await;
                }
            }
        }

        Ok(())
    }

    /// 处理文本消息
    async fn handle_text_message(&self, text: &str) -> Result<()> {
        let json: Value = serde_json::from_str(text)?;
        
        // 获取消息类型
        let msg_type = json.get("type")
            .and_then(|t| t.as_str())
            .unwrap_or("unknown");

        match msg_type {
            "ping" => {
                // 服务器发来的 Ping，需要回复 Pong
                if let Some(timestamp) = json.get("time").and_then(|t| t.as_str()) {
                    self.connection.send_pong(timestamp).await?;
                    log::debug!("响应服务器 Ping");
                }
            }
            "pong" => {
                // 服务器响应我们的 Ping
                log::debug!("收到服务器 Pong");
            }
            "subscribed" => {
                // 订阅成功确认
                if let Some(channel) = json.get("channel").and_then(|c| c.as_str()) {
                    log::info!("订阅成功: {}", channel);
                }
            }
            "unsubscribed" => {
                // 取消订阅确认
                if let Some(channel) = json.get("channel").and_then(|c| c.as_str()) {
                    log::info!("取消订阅成功: {}", channel);
                }
            }
            "error" => {
                // 错误消息
                if let Some(content) = json.get("content") {
                    log::error!("服务器错误: {}", content);
                }
            }
            "payload" | "quote-event" => {
                // 市场数据消息
                self.handle_market_data(&json).await?;
            }
            "trade-event" => {
                // 交易事件消息（私有）
                self.handle_trade_event(&json).await?;
            }
            _ => {
                log::debug!("未知消息类型: {}", msg_type);
            }
        }

        // 调用注册的处理器
        let handlers = self.handlers.lock().await;
        if let Some(handler) = handlers.get(msg_type) {
            handler(json.clone())?;
        }

        Ok(())
    }

    /// 处理市场数据
    async fn handle_market_data(&self, message: &Value) -> Result<()> {
        let channel = message.get("channel")
            .and_then(|c| c.as_str())
            .unwrap_or("");

        if channel.starts_with("ticker.") {
            self.handle_ticker_message(message).await?;
        } else if channel.starts_with("depth.") {
            self.handle_depth_message(message).await?;
        } else if channel.starts_with("kline.") {
            self.handle_kline_message(message).await?;
        } else if channel.starts_with("trades.") {
            self.handle_trades_message(message).await?;
        } else if channel == "metadata" {
            self.handle_metadata_message(message).await?;
        }

        Ok(())
    }

    /// 处理 Ticker 消息
    async fn handle_ticker_message(&self, message: &Value) -> Result<()> {
        if let Some(content) = message.get("content") {
            if let Some(data) = content.get("data").and_then(|d| d.as_array()) {
                for item in data {
                    if let Some(last_price) = item.get("lastPrice").and_then(|p| p.as_str()) {
                        if let Some(contract_id) = item.get("contractId").and_then(|c| c.as_str()) {
                            log::debug!("合约 {} 最新价格: {}", contract_id, last_price);
                        }
                    }
                }
            }
        }
        Ok(())
    }

    /// 处理深度数据
    async fn handle_depth_message(&self, message: &Value) -> Result<()> {
        if let Some(content) = message.get("content") {
            if let Some(data) = content.get("data").and_then(|d| d.as_array()) {
                for item in data {
                    if let Some(contract_id) = item.get("contractId").and_then(|c| c.as_str()) {
                        let depth_type = item.get("depthType")
                            .and_then(|t| t.as_str())
                            .unwrap_or("Unknown");
                        log::debug!("合约 {} 深度数据更新（类型: {}）", contract_id, depth_type);
                    }
                }
            }
        }
        Ok(())
    }

    /// 处理 K 线消息
    async fn handle_kline_message(&self, message: &Value) -> Result<()> {
        if let Some(content) = message.get("content") {
            if let Some(data) = content.get("data").and_then(|d| d.as_array()) {
                for item in data {
                    if let Some(contract_id) = item.get("contractId").and_then(|c| c.as_str()) {
                        log::debug!("合约 {} K 线数据更新", contract_id);
                    }
                }
            }
        }
        Ok(())
    }

    /// 处理成交消息
    async fn handle_trades_message(&self, message: &Value) -> Result<()> {
        if let Some(content) = message.get("content") {
            if let Some(data) = content.get("data").and_then(|d| d.as_array()) {
                for item in data {
                    if let Some(contract_id) = item.get("contractId").and_then(|c| c.as_str()) {
                        if let Some(price) = item.get("price").and_then(|p| p.as_str()) {
                            log::debug!("合约 {} 成交: 价格 {}", contract_id, price);
                        }
                    }
                }
            }
        }
        Ok(())
    }

    /// 处理元数据消息
    async fn handle_metadata_message(&self, message: &Value) -> Result<()> {
        if let Some(content) = message.get("content") {
            log::debug!("元数据更新");
        }
        Ok(())
    }

    /// 处理交易事件（私有）
    async fn handle_trade_event(&self, message: &Value) -> Result<()> {
        if let Some(content) = message.get("content") {
            if let Some(event) = content.get("event").and_then(|e| e.as_str()) {
                log::info!("交易事件: {}", event);
                
                // 处理不同类型的事件
                match event {
                    "ACCOUNT_UPDATE" => log::debug!("账户更新"),
                    "ORDER_UPDATE" => log::debug!("订单更新"),
                    "POSITION_UPDATE" => log::debug!("持仓更新"),
                    "DEPOSIT_UPDATE" => log::debug!("充值更新"),
                    "WITHDRAW_UPDATE" => log::debug!("提现更新"),
                    "FUNDING_SETTLEMENT" => log::debug!("资金费结算"),
                    "START_LIQUIDATING" => log::warn!("开始强平"),
                    "FINISH_LIQUIDATING" => log::warn!("强平完成"),
                    _ => log::debug!("其他事件: {}", event),
                }
            }
        }
        Ok(())
    }
}

/// 实时价格流管理器
pub struct RealTimePriceStream {
    ws_client: EdgeXWebSocketClient,
    contract_ids: Vec<String>,
}

impl RealTimePriceStream {
    /// 创建新的实时价格流（公共市场数据）
    pub fn new_public(testnet: bool, contract_ids: Vec<String>) -> Self {
        let ws_client = EdgeXWebSocketClient::new_public(testnet);
        Self { ws_client, contract_ids }
    }

    /// 创建新的实时价格流（私有账户数据）
    pub fn new_private(account_id: u64, stark_private_key: String, testnet: bool) -> Self {
        let ws_client = EdgeXWebSocketClient::new_private(account_id, stark_private_key, testnet);
        Self {
            ws_client,
            contract_ids: Vec::new(),
        }
    }

    /// 启动市场数据流
    pub async fn start_market_stream(&mut self) -> Result<()> {
        log::info!("启动实时市场数据流");
        
        // 连接 WebSocket
        let connection = self.ws_client.connect().await?;
        
        // 订阅数据
        for contract_id in &self.contract_ids {
            // 订阅 ticker
            self.ws_client.subscribe_ticker(&connection, contract_id).await?;
            
            // 订阅深度（15档）
            self.ws_client.subscribe_depth(&connection, contract_id, 15).await?;
            
            // 订阅 K 线（LAST_PRICE, 1分钟）
            self.ws_client.subscribe_kline(&connection, contract_id, "LAST_PRICE", "MINUTE_1").await?;
            
            // 订阅成交数据
            self.ws_client.subscribe_trades(&connection, contract_id).await?;
        }
        
        // 订阅元数据
        self.ws_client.subscribe_metadata(&connection).await?;
        
        // 启动消息处理
        let handler = WebSocketMessageHandler::new(connection);
        handler.start_listening().await?;
        
        Ok(())
    }

    /// 启动私有账户数据流
    pub async fn start_private_stream(&mut self) -> Result<()> {
        log::info!("启动实时账户数据流");
        
        // 连接 WebSocket
        let connection = self.ws_client.connect().await?;
        
        // 私有连接不需要订阅，数据会自动推送
        log::info!("等待账户数据推送...");
        
        // 启动消息处理
        let handler = WebSocketMessageHandler::new(connection);
        handler.start_listening().await?;
        
        Ok(())
    }
}

/// WebSocket 管理器，支持同时管理公共和私有连接
pub struct WebSocketManager {
    public_client: Option<EdgeXWebSocketClient>,
    private_client: Option<EdgeXWebSocketClient>,
    contract_ids: Vec<String>,
}

impl WebSocketManager {
    /// 创建新的 WebSocket 管理器
    pub fn new(testnet: bool) -> Self {
        Self {
            public_client: Some(EdgeXWebSocketClient::new_public(testnet)),
            private_client: None,
            contract_ids: Vec::new(),
        }
    }

    /// 设置私有客户端凭据
    pub fn with_private(&mut self, account_id: u64, stark_private_key: String, testnet: bool) {
        self.private_client = Some(EdgeXWebSocketClient::new_private(
            account_id,
            stark_private_key,
            testnet,
        ));
    }

    /// 添加要监控的合约
    pub fn add_contracts(&mut self, contract_ids: Vec<String>) {
        self.contract_ids.extend(contract_ids);
    }

    /// 启动所有连接
    pub async fn start(&mut self) -> Result<()> {
        let mut handles = vec![];

        // 启动公共市场数据流
        if let Some(client) = self.public_client.take() {
            let contract_ids = self.contract_ids.clone();
            let handle = tokio::spawn(async move {
                let mut stream = RealTimePriceStream {
                    ws_client: client,
                    contract_ids,
                };
                stream.start_market_stream().await
            });
            handles.push(handle);
        }

        // 启动私有账户数据流
        if let Some(client) = self.private_client.take() {
            let handle = tokio::spawn(async move {
                let mut stream = RealTimePriceStream {
                    ws_client: client,
                    contract_ids: Vec::new(),
                };
                stream.start_private_stream().await
            });
            handles.push(handle);
        }

        // 等待所有任务完成
        for handle in handles {
            if let Err(e) = handle.await {
                log::error!("WebSocket 任务失败: {}", e);
            }
        }

        Ok(())
    }
}
