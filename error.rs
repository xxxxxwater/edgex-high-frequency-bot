use thiserror::Error;

#[derive(Error, Debug)]
pub enum StrategyError {
    #[error("API错误: {0}")]
    ApiError(String),
    
    #[error("网络错误: {0}")]
    NetworkError(#[from] reqwest::Error),
    
    #[error("JSON解析错误: {0}")]
    JsonError(#[from] serde_json::Error),
    
    #[error("交易错误: {0}")]
    TradingError(String),
    
    #[error("风控触发: {0}")]
    RiskControlTriggered(String),
}

impl From<StrategyError> for anyhow::Error {
    fn from(error: StrategyError) -> Self {
        anyhow::anyhow!(error.to_string())
    }
}