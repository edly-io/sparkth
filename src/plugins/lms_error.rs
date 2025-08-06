use thiserror::Error;

use crate::plugins::config::ConfigError;

#[derive(Error, Debug)]
pub enum CanvasError {
    #[error("Canvas API Error ({status_code}): {message}")]
    Api { status_code: u16, message: String },
    #[error("HTTP request failed: {0}")]
    Request(#[from] reqwest::Error),
    #[error("JSON parsing failed: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Error, Debug)]
pub enum LmsError {
    #[error(transparent)]
    CanvasError(#[from] CanvasError),
    #[error(transparent)]
    ConfigError(#[from] ConfigError),
}

