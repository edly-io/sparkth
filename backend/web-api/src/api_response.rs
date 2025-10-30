use app_core::CoreError;

use axum::{body::Body, http::StatusCode, response::IntoResponse};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Serialize, Deserialize, Debug)]
pub struct ApiResponse {
    pub response_data: Option<Value>,
    pub message: String,
    pub status: u16,
}

impl IntoResponse for ApiResponse {
    fn into_response(self) -> axum::http::Response<Body> {
        let response_data = serde_json::to_vec(&self).unwrap();
        axum::http::Response::builder()
            .status(self.status)
            .header("Content-Type", "application/json")
            .body(Body::from(response_data))
            .unwrap()
    }
}

impl ApiResponse {
    pub fn new(response_data: Option<Value>, message: String, code: StatusCode) -> Self {
        Self {
            response_data,
            message,
            status: code.as_u16(),
        }
    }

    pub fn err(response_data: Option<Value>, error: CoreError) -> Self {
        let (message, status): (String, StatusCode) = match error {
            CoreError::NotFound(_) => ("Record not found".to_string(), StatusCode::NOT_FOUND),
            CoreError::PooledConnection(_) => (
                "Database connection timed out".to_string(),
                StatusCode::GATEWAY_TIMEOUT,
            ),
            CoreError::QueryBuilder(_) => (
                "Data is not sent in request".to_string(),
                StatusCode::NOT_MODIFIED,
            ),
            _ => (
                "Could not process request - Server Error".to_string(),
                StatusCode::INTERNAL_SERVER_ERROR,
            ),
        };

        Self {
            response_data,
            message,
            status: status.into(),
        }
    }
}
