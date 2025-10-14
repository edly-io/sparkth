use core::db::error::CoreError;

use axum::{Json, http::StatusCode};
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, PartialEq, Debug, Clone)]
pub struct ApiResponse<T: Serialize> {
    pub response_code: u16,
    pub response_message: String,
    data: T,
}

pub type ApiJsonResult<T> = Result<Json<ApiResponse<T>>, CoreError>;

impl<T: Serialize> ApiResponse<T> {
    pub fn ok(data: T, response_message: &str) -> ApiJsonResult<T> {
        Ok(Json(ApiResponse {
            response_code: StatusCode::OK.as_u16(),
            response_message: String::from(response_message),
            data,
        }))
    }

    pub fn to_data(self) -> T {
        self.data
    }
}

impl ApiResponse<()> {
    pub fn err(status: StatusCode, response_message: &str) -> ApiResponse<()> {
        ApiResponse {
            response_code: status.as_u16(),
            response_message: String::from(response_message),
            data: (),
        }
    }
}
