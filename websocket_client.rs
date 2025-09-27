use crate::types::*;
use anyhow::Result;
use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use url::Url;

pub struct EdgeXWebSocketClient {
    base_url: String,
    api_key: String,
    secret_key: String,
    is_connected: bool,
}

impl EdgeXWebSocketClient {
    pub fn new(api_key: String, secret_key: String, testnet: bool) -> Self {
        let base_url = if testnet {
            "wss://testnet.edgex.com/ws".to_string()
        } else {
            "wss://api.edgex.com/ws".to_string()
        };

        Self {
            base_url,
            api_key,
            secret_key,
            is_connected: false,
        }
    }

    pub async fn connect(&mut self) -> Result<WebSocketConnection> {
        let url = Url::parse(&self.base_url)?;
        let (ws_stream, _) = connect_async(url).await?;
        
        let (mut write, read) = ws_stream.split();
        
        // 發送認證消息
        let auth_message = serde_json::json!({
            "method": "auth",
            "api_key": self.api_key,
            "secret_key": self.secret_key
        });
        
        write.send(Message::Text(auth_message.to_string())).await?;
        
        self.is_connected = true;
        
        Ok(WebSocketConnection {
            write: Arc::new(Mutex::new(write)),
            read: Arc::new(Mutex::new(read)),
        })
    }

    pub async fn subscribe_ticker(&self, connection: &WebSocketConnection, symbols: &[String]) -> Result<()> {
        let mut write = connection.write.lock().await;
        
        for symbol in symbols {
            let subscribe_message = serde_json::json!({
                "method": "subscribe",
                "channel": "ticker",
                "symbol": symbol
            });
            
            write.send(Message::Text(subscribe_message.to_string())).await?;
            log::info!("訂閱 {} 的ticker數據", symbol);
        }
        
        Ok(())
    }

    pub async fn subscribe_depth(&self, connection: &WebSocketConnection, symbols: &[String]) -> Result<()> {
        let mut write = connection.write.lock().await;
        
        for symbol in symbols {
            let subscribe_message = serde_json::json!({
                "method": "subscribe",
                "channel": "depth",
                "symbol": symbol
            });
            
            write.send(Message::Text(subscribe_message.to_string())).await?;
            log::info!("訂閱 {} 的深度數據", symbol);
        }
        
        Ok(())
    }

    pub async fn subscribe_kline(&self, connection: &WebSocketConnection, symbols: &[String], interval: &str) -> Result<()> {
        let mut write = connection.write.lock().await;
        
        for symbol in symbols {
            let subscribe_message = serde_json::json!({
                "method": "subscribe",
                "channel": "kline",
                "symbol": symbol,
                "interval": interval
            });
            
            write.send(Message::Text(subscribe_message.to_string())).await?;
            log::info!("訂閱 {} 的K線數據，間隔: {}", symbol, interval);
        }
        
        Ok(())
    }
}

use tokio_tungstenite::tungstenite::stream::SplitSink;
use tokio_tungstenite::tungstenite::stream::SplitStream;
use tokio_tungstenite::WebSocketStream;
use tokio_tungstenite::MaybeTlsStream;
use tokio::net::TcpStream;

pub struct WebSocketConnection {
    pub write: Arc<Mutex<SplitSink<WebSocketStream<MaybeTlsStream<TcpStream>>, Message>>>,
    pub read: Arc<Mutex<SplitStream<WebSocketStream<MaybeTlsStream<TcpStream>>>>>,
}

pub struct WebSocketMessageHandler {
    connection: WebSocketConnection,
}

impl WebSocketMessageHandler {
    pub fn new(connection: WebSocketConnection) -> Self {
        Self { connection }
    }

    pub async fn start_listening(&mut self) -> Result<()> {
        let mut read = self.connection.read.lock().await;
        
        while let Some(message) = read.next().await {
            match message {
                Ok(Message::Text(text)) => {
                    if let Ok(json) = serde_json::from_str::<Value>(&text) {
                        self.handle_message(&json).await?;
                    }
                }
                Ok(Message::Ping(data)) => {
                    // 回應Ping消息
                    let mut write = self.connection.write.lock().await;
                    write.send(Message::Pong(data)).await?;
                }
                Ok(Message::Close(_)) => {
                    log::info!("WebSocket連接關閉");
                    break;
                }
                Err(e) => {
                    log::error!("WebSocket錯誤: {}", e);
                    break;
                }
                _ => {}
            }
        }
        
        Ok(())
    }

    async fn handle_message(&self, message: &Value) -> Result<()> {
        if let Some(channel) = message.get("channel").and_then(|c| c.as_str()) {
            match channel {
                "ticker" => self.handle_ticker_message(message).await?,
                "depth" => self.handle_depth_message(message).await?,
                "kline" => self.handle_kline_message(message).await?,
                _ => log::debug!("未知頻道: {}", channel),
            }
        }
        
        Ok(())
    }

    async fn handle_ticker_message(&self, message: &Value) -> Result<()> {
        if let (Some(symbol), Some(last_price)) = (
            message.get("symbol").and_then(|s| s.as_str()),
            message.get("last_price").and_then(|p| p.as_f64()),
        ) {
            log::debug!("{} 最新價格: {}", symbol, last_price);
            // 這裡可以觸發交易信號生成
        }
        Ok(())
    }

    async fn handle_depth_message(&self, message: &Value) -> Result<()> {
        if let Some(symbol) = message.get("symbol").and_then(|s| s.as_str()) {
            log::debug!("{} 深度數據更新", symbol);
            // 分析市場深度，計算支撐阻力位
        }
        Ok(())
    }

    async fn handle_kline_message(&self, message: &Value) -> Result<()> {
        if let (Some(symbol), Some(kline_data)) = (
            message.get("symbol").and_then(|s| s.as_str()),
            message.get("kline"),
        ) {
            log::debug!("{} K線數據更新", symbol);
            // 更新K線數據，用於技術分析
        }
        Ok(())
    }
}

pub struct RealTimePriceStream {
    ws_client: EdgeXWebSocketClient,
    symbols: Vec<String>,
}

impl RealTimePriceStream {
    pub fn new(api_key: String, secret_key: String, testnet: bool, symbols: Vec<String>) -> Self {
        let ws_client = EdgeXWebSocketClient::new(api_key, secret_key, testnet);
        Self { ws_client, symbols }
    }

    pub async fn start_stream(&mut self) -> Result<()> {
        log::info!("啟動實時價格流");
        
        // 連接WebSocket
        let connection = self.ws_client.connect().await?;
        
        // 訂閱數據
        self.ws_client.subscribe_ticker(&connection, &self.symbols).await?;
        self.ws_client.subscribe_depth(&connection, &self.symbols).await?;
        self.ws_client.subscribe_kline(&connection, &self.symbols, "1m").await?;
        
        // 啟動消息處理
        let mut handler = WebSocketMessageHandler::new(connection);
        handler.start_listening().await?;
        
        Ok(())
    }
}
