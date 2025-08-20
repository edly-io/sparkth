use thiserror::Error;

#[derive(Debug)]
pub enum OpenEdxError {
    Http(reqwest::Error),
    Json(serde_json::Error),
    Authentication(String),
    Api { status_code: u16, message: String },
}
impl From<reqwest::Error> for OpenEdxError {
    fn from(e: reqwest::Error) -> Self {
        OpenEdxError::Http(e)
    }
}
impl From<serde_json::Error> for OpenEdxError {
    fn from(e: serde_json::Error) -> Self {
        OpenEdxError::Json(e)
    }
}
impl std::fmt::Display for OpenEdxError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OpenEdxError::Http(e) => write!(f, "http: {e}"),
            OpenEdxError::Json(e) => write!(f, "json: {e}"),
            OpenEdxError::Authentication(s) => write!(f, "auth: {s}"),
            OpenEdxError::Api {
                status_code,
                message,
            } => write!(f, "api {status_code}: {message}"),
        }
    }
}
impl std::error::Error for OpenEdxError {}
