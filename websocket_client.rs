use futures_util::{SinkExt, StreamExt};
use tokio::net::TcpStream;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message, MaybeTlsStream, WebSocketStream};
use serde_json::{Value, json};
use url::Url;
use log::{info, warn, error};
use std::collections::HashMap;
use tokio::sync::mpsc;
use crate::types::PriceData;

pub struct EdgeXWebSocketClient {
    ws_stream: Option<WebSocketStream<MaybeTlsStream<TcpStream>>>,
    symbol: String,
    timeframe: String,
    kline_buffer: Vec<PriceData>,
    buffer_size: usize,
    price_receiver: Option<mpsc::UnboundedReceiver<PriceData>>,
    price_sender: mpsc::UnboundedSender<PriceData>,
}

impl EdgeXWebSocketClient {
    pub fn new(symbol: String, timeframe: String, buffer_size: usize) -> Self {
        let (price_sender, price_receiver) = mpsc::unbounded_channel();
        
        Self {
            ws_stream: None,
            symbol,
            timeframe,
            kline_buffer: Vec::with_capacity(buffer_size),
            buffer_size,
            price_receiver: Some(price_receiver),
            price_sender,
        }
    }

    pub async fn connect(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let url = Url::parse("wss://api.edgex.com/ws")?;
        
        match connect_async(url).await {
            Ok((stream, response)) => {
                info!("WebSocket连接成功: {:?}", response.status());
                self.ws_stream = Some(stream);
                self.authenticate().await?;
                self.subscribe_kline().await?;
                Ok(())
            }
            Err(e) => {
                error!("WebSocket连接失败: {}", e);
                Err(Box::new(e))
            }
        }
    }

    async fn authenticate(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        // 如果需要认证，实现认证逻辑
        // 根据EdgeX文档实现
        Ok(())
    }

    async fn subscribe_kline(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let subscribe_msg = json!({
            "method": "SUBSCRIBE",
            "params": [format!("{}@kline_{}", self.symbol, self.timeframe)],
            "id": 1
        });

        if let Some(stream) = &mut self.ws_stream {
            stream.send(Message::Text(subscribe_msg.to_string())).await?;
            info!("已订阅K线数据: {} {}", self.symbol, self.timeframe);
        }
        
        Ok(())
    }

    pub async fn start_listening(&mut self) {
        if let Some(stream) = &mut self.ws_stream {
            while let Some(message) = stream.next().await {
                match message {
                    Ok(Message::Text(text)) => {
                        if let Err(e) = self.handle_message(&text).await {
                            error!("处理WebSocket消息错误: {}", e);
                        }
                    }
                    Ok(Message::Ping(data)) => {
                        if let Some(stream) = &mut self.ws_stream {
                            let _ = stream.send(Message::Pong(data)).await;
                        }
                    }
                    Err(e) => {
                        error!("WebSocket接收错误: {}", e);
                        break;
                    }
                    _ => {}
                }
            }
        }
        
        // 连接断开，尝试重连
        self.handle_reconnection().await;
    }

    async fn handle_message(&mut self, message: &str) -> Result<(), Box<dyn std::error::Error>> {
        let value: Value = serde_json::from_str(message)?;
        
        // 根据EdgeX WebSocket协议解析K线数据
        if let Some(kline_data) = self.parse_kline_data(&value) {
            self.update_kline_buffer(kline_data).await;
            
            // 发送价格更新
            if let Err(e) = self.price_sender.send(kline_data) {
                error!("发送价格数据失败: {}", e);
            }
        }
        
        Ok(())
    }

    fn parse_kline_data(&self, value: &Value) -> Option<PriceData> {
        // 根据EdgeX WebSocket协议解析
        // 示例格式，需要根据实际API调整
        if let (Some(stream), Some(kline)) = (value.get("stream"), value.get("data")) {
            if stream.as_str()?.contains(&format!("{}@kline_{}", self.symbol, self.timeframe)) {
                return Some(PriceData {
                    timestamp: kline["t"].as_i64()?,
                    open: kline["o"].as_str()?.parse().ok()?,
                    high: kline["h"].as_str()?.parse().ok()?,
                    low: kline["l"].as_str()?.parse().ok()?,
                    close: kline["c"].as_str()?.parse().ok()?,
                    volume: kline["v"].as_str()?.parse().ok()?,
                });
            }
        }
        
        None
    }

    async fn update_kline_buffer(&mut self, new_kline: PriceData) {
        // 检查是否是新的K线（基于时间戳）
        if let Some(last_kline) = self.kline_buffer.last() {
            if new_kline.timestamp <= last_kline.timestamp {
                // 更新当前K线
                if let Some(last) = self.kline_buffer.last_mut() {
                    *last = new_kline;
                }
                return;
            }
        }
        
        // 添加新K线
        self.kline_buffer.push(new_kline);
        
        // 保持缓冲区大小
        if self.kline_buffer.len() > self.buffer_size {
            self.kline_buffer.remove(0);
        }
        
        info!("K线缓冲区更新: {} 根K线", self.kline_buffer.len());
    }

    pub fn get_kline_receiver(&mut self) -> Option<mpsc::UnboundedReceiver<PriceData>> {
        self.price_receiver.take()
    }

    pub fn get_current_klines(&self, count: usize) -> Vec<PriceData> {
        let start_idx = if self.kline_buffer.len() > count {
            self.kline_buffer.len() - count
        } else {
            0
        };
        
        self.kline_buffer[start_idx..].to_vec()
    }

    async fn handle_reconnection(&mut self) {
        warn!("WebSocket连接断开，尝试重连...");
        
        for attempt in 1..=5 {
            match self.connect().await {
                Ok(_) => {
                    info!("WebSocket重连成功");
                    break;
                }
                Err(e) => {
                    error!("重连尝试 {} 失败: {}", attempt, e);
                    tokio::time::sleep(tokio::time::Duration::from_secs(attempt * 2)).await;
                }
            }
        }
    }
}