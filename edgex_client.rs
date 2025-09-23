use crate::types::*;
use anyhow::Result;
use chrono::{DateTime, Utc};
use hmac::{Hmac, Mac};
use reqwest::Client;
use serde_json::Value;
use sha2::Sha256;
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

type HmacSha256 = Hmac<Sha256>;

pub struct EdgeXClient {
    client: Client,
    base_url: String,
    api_key: String,
    secret_key: String,
}

impl EdgeXClient {
    pub fn new(api_key: String, secret_key: String, testnet: bool) -> Self {
        let base_url = if testnet {
            "https://testnet.edgex.com".to_string()
        } else {
            "https://api.edgex.com".to_string()
        };

        Self {
            client: Client::new(),
            base_url,
            api_key,
            secret_key,
        }
    }

    fn generate_signature(&self, timestamp: u64, method: &str, endpoint: &str, body: &str) -> String {
        let message = format!("{}{}{}{}", timestamp, method, endpoint, body);
        let mut mac = HmacSha256::new_from_slice(self.secret_key.as_bytes())
            .expect("HMAC can take key of any size");
        mac.update(message.as_bytes());
        let result = mac.finalize();
        hex::encode(result.into_bytes())
    }

    fn get_timestamp(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64
    }

    pub async fn get_account_info(&self) -> Result<AccountInfo> {
        let timestamp = self.get_timestamp();
        let endpoint = "/api/v1/account";
        let signature = self.generate_signature(timestamp, "GET", endpoint, "");

        let response = self.client
            .get(&format!("{}{}", self.base_url, endpoint))
            .header("X-EDGEX-APIKEY", &self.api_key)
            .header("X-EDGEX-TIMESTAMP", timestamp.to_string())
            .header("X-EDGEX-SIGNATURE", signature)
            .send()
            .await?;

        let json: Value = response.json().await?;
        
        // 解析账户信息
        let balance = json["balance"].as_f64().unwrap_or(0.0);
        let available_balance = json["availableBalance"].as_f64().unwrap_or(0.0);
        
        Ok(AccountInfo {
            balance,
            available_balance,
            positions: HashMap::new(),
        })
    }

    pub async fn get_klines(&self, symbol: &str, interval: &str, limit: u32) -> Result<Vec<PriceData>> {
        let endpoint = format!("/api/v1/klines?symbol={}&interval={}&limit={}", symbol, interval, limit);
        
        let response = self.client
            .get(&format!("{}{}", self.base_url, endpoint))
            .send()
            .await?;

        let json: Value = response.json().await?;
        
        let mut klines = Vec::new();
        if let Value::Array(arr) = json {
            for item in arr {
                if let Value::Array(kline) = item {
                    let price_data = PriceData {
                        timestamp: kline[0].as_i64().unwrap_or(0),
                        open: kline[1].as_str().unwrap_or("0").parse().unwrap_or(0.0),
                        high: kline[2].as_str().unwrap_or("0").parse().unwrap_or(0.0),
                        low: kline[3].as_str().unwrap_or("0").parse().unwrap_or(0.0),
                        close: kline[4].as_str().unwrap_or("0").parse().unwrap_or(0.0),
                        volume: kline[5].as_str().unwrap_or("0").parse().unwrap_or(0.0),
                    };
                    klines.push(price_data);
                }
            }
        }
        
        Ok(klines)
    }

    pub async fn place_order(&self, order: &Order) -> Result<Value> {
        let timestamp = self.get_timestamp();
        let endpoint = "/api/v1/order";
        
        let mut body = HashMap::new();
        body.insert("symbol", order.symbol.clone());
        body.insert("side", match order.side {
            OrderSide::Buy => "BUY".to_string(),
            OrderSide::Sell => "SELL".to_string(),
        });
        body.insert("type", match order.order_type {
            OrderType::Market => "MARKET".to_string(),
            OrderType::Limit => "LIMIT".to_string(),
        });
        body.insert("quantity", order.quantity.to_string());
        if let Some(price) = order.price {
            body.insert("price", price.to_string());
        }
        body.insert("leverage", order.leverage.to_string());

        let body_json = serde_json::to_string(&body)?;
        let signature = self.generate_signature(timestamp, "POST", endpoint, &body_json);

        let response = self.client
            .post(&format!("{}{}", self.base_url, endpoint))
            .header("X-EDGEX-APIKEY", &self.api_key)
            .header("X-EDGEX-TIMESTAMP", timestamp.to_string())
            .header("X-EDGEX-SIGNATURE", signature)
            .header("Content-Type", "application/json")
            .body(body_json)
            .send()
            .await?;

        let result: Value = response.json().await?;
        Ok(result)
    }

    pub async fn set_leverage(&self, symbol: &str, leverage: u32) -> Result<Value> {
        let timestamp = self.get_timestamp();
        let endpoint = "/api/v1/leverage";
        
        let mut body = HashMap::new();
        body.insert("symbol", symbol.to_string());
        body.insert("leverage", leverage.to_string());

        let body_json = serde_json::to_string(&body)?;
        let signature = self.generate_signature(timestamp, "POST", endpoint, &body_json);

        let response = self.client
            .post(&format!("{}{}", self.base_url, endpoint))
            .header("X-EDGEX-APIKEY", &self.api_key)
            .header("X-EDGEX-TIMESTAMP", timestamp.to_string())
            .header("X-EDGEX-SIGNATURE", signature)
            .header("Content-Type", "application/json")
            .body(body_json)
            .send()
            .await?;

        let result: Value = response.json().await?;
        Ok(result)
    }
}

