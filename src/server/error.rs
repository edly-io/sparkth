use thiserror::Error;

#[derive(Error, Debug)]
pub enum CanvasError {
    #[error("Canvas API Error ({status_code}): {message}")]
    ApiError { status_code: u16, message: String },
    #[error("HTTP request failed: {0}")]
    RequestError(#[from] reqwest::Error),
    #[error("JSON parsing failed: {0}")]
    JsonError(#[from] serde_json::Error),
    #[error("Invalid HTTP method: {0}")]
    InvalidMethod(String),
}

#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Environment variable not found: {0}")]
    EnvVarNotFound(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("env not found")]
    EnvNotFound(#[from] dotenvy::Error),
}
