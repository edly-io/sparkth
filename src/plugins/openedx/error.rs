use thiserror::Error;

#[derive(Debug, Error)]
pub enum OpenEdxError {
    #[error("Authentication failed: {0}")]
    Authentication(String),
    #[error("OpenEdx API Error ({status_code}): {message}")]
    Api { status_code: u16, message: String },
    #[error("HTTP request failed: {0}")]
    Request(#[from] reqwest::Error),
    #[error("JSON parsing failed: {0}")]
    Json(#[from] serde_json::Error),
    #[error("Url parsing failed: {0}")]
    UrlParse(#[from] url::ParseError),
}
