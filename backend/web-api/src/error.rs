// use core::db::error::CoreError;

// use axum::http::StatusCode;
// use thiserror::Error;

// #[derive(Error, Debug)]
// pub enum ApiError {
//     #[error("{0}")]
//     Core(#[source] CoreError),

//     #[error("{0}")]
//     Internal(String),

//     #[error("{0}")]
//     Unauthorized(String),

//     #[error("{0}")]
//     NotFound(String),

//     #[error("{0}")]
//     BadRequest(String),
// }

// // pub fn get_http_status() -> StatusCode {
// //         match self {
// //             APIError::Core(core_error) => get_core_error_status(core_error),
// //             APIError::Internal(_) => Status::InternalServerError,
// //             APIError::NotFound(_) => Status::NotFound,
// //             APIError::Unauthorized(_) => Status::Unauthorized,
// //             APIError::UserNotFoundWeb(_) => Status::NotFound,
// //             APIError::UserNotFoundMobile(_) => Status::NotFound,
// //             APIError::BadRequest(_) => Status::BadRequest,
// //             APIError::WrongPassword(_) => Status::BadRequest,
// //             APIError::InvalidOTP(_) => Status::Unauthorized,
// //             APIError::Forbidden(_) => Status::Forbidden,
// //             APIError::OTPExpired(_) => Status::Unauthorized,
// //             APIError::StripeError(_) => Status::InternalServerError,
// //         }
// //     }
