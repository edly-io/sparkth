use serde::{Deserialize, Serialize};
use std::env;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Environment variable not found: {0}")]
    EnvVarNotFound(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanvasConfig {
    pub api_url: String,
    pub api_token: String,
}

impl Default for CanvasConfig {
    fn default() -> Self {
        Self {
            api_url: String::new(),
            api_token: String::new(),
        }
    }
}

impl CanvasConfig {
    pub fn from_env() -> Result<Self, ConfigError> {
        let api_url = env::var("CANVAS_API_URL")
            .map_err(|_| ConfigError::EnvVarNotFound("CANVAS_API_URL".to_string()))?;
        let api_token = env::var("CANVAS_API_TOKEN")
            .map_err(|_| ConfigError::EnvVarNotFound("CANVAS_API_TOKEN".to_string()))?;

        Ok(Self { api_url, api_token })
    }
}
