use std::env;

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Environment variable not found: {0}")]
    EnvVarNotFound(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("env not found")]
    EnvNotFound(#[from] dotenvy::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub base_url: String,
    pub api_key: Option<String>,
    pub client_id: Option<String>,
    pub client_secret: Option<String>,
}

impl Config {
    pub fn from_env() -> Result<Self, ConfigError> {
        let api_url = env::var("API_URL")
            .map_err(|_| ConfigError::EnvVarNotFound("API_URL".to_string()))?;
        let api_token = env::var("API_TOKEN")
            .map_err(|_| ConfigError::EnvVarNotFound("API_TOKEN".to_string()))?;

        Ok(Self { 
            base_url: api_url, 
            api_key: Some(api_token),  
            client_id: None, 
            client_secret: None
        })
    }
}