use axum::{Json, extract::State, http::StatusCode, response::IntoResponse};
use serde::{Deserialize, Serialize};
use serde_json::to_value;

use crate::api_response::ApiResponse;
use crate::jwt::JWTService;

use app_core::UserService;

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    email: String,
    password: String,
}

#[derive(Debug, Deserialize)]
pub struct TokenRequest {
    refresh_token: String,
}

#[derive(Debug, Serialize)]
struct AuthResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserInfo,
}

#[derive(Debug, Serialize)]
struct AccessTokenResponse {
    pub access_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserInfo,
}

#[derive(Debug, Serialize)]
struct RefreshTokenResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserInfo,
}

#[derive(Debug, Serialize)]
struct UserInfo {
    pub id: i32,
    pub username: String,
    pub email: String,
    pub role: String,
}

#[axum::debug_handler]
pub async fn get_test_token(
    State((user_service, jwt_service)): State<(UserService, JWTService)>,
) -> impl IntoResponse {
    let all_users = user_service.get_users().expect("Failed to get users");
    let user = all_users
        .into_iter()
        .find(|u| u.is_active)
        .expect("No active users found - please create an active user first");

    let access_token = jwt_service
        .encode_access_token(&user)
        .expect("Failed to encode access token");

    let refresh_token = jwt_service
        .encode_refresh_token(&user.id.to_string())
        .expect("Failed to encode refresh token");

    let response = AuthResponse {
        access_token,
        refresh_token,
        token_type: "Bearer".to_string(),
        expires_in: jwt_service.get_expiration_hours() * 3600, // Convert hours to seconds
        user: UserInfo {
            id: user.id,
            username: user.username,
            email: user.email,
            role: if user.is_admin {
                "admin".to_string()
            } else {
                "user".to_string()
            },
        },
    };

    Json(response)
}

#[axum::debug_handler]
pub async fn login(
    State((user_service, jwt_service)): State<(UserService, JWTService)>,
    Json(request): Json<LoginRequest>,
) -> impl IntoResponse {
    let auth_response = user_service.authenticate(request.email, request.password);

    let response = match auth_response {
        Ok(user) => {
            let access_token = match jwt_service.encode_access_token(&user) {
                Ok(token) => token,
                Err(_) => {
                    return Json(ApiResponse {
                        response_data: None,
                        message: "Failed to generate access token".to_string(),
                        status: StatusCode::INTERNAL_SERVER_ERROR.into(),
                    });
                }
            };

            let refresh_token = match jwt_service.encode_refresh_token(&user.id.to_string()) {
                Ok(token) => token,
                Err(_) => {
                    return Json(ApiResponse {
                        response_data: None,
                        message: "Failed to generate refresh token".to_string(),
                        status: StatusCode::INTERNAL_SERVER_ERROR.into(),
                    });
                }
            };

            let response = AuthResponse {
                access_token,
                refresh_token,
                token_type: "Bearer".to_string(),
                expires_in: jwt_service.get_expiration_hours() * 3600,
                user: UserInfo {
                    id: user.id,
                    username: user.username,
                    email: user.email,
                    role: if user.is_admin {
                        "admin".to_string()
                    } else {
                        "user".to_string()
                    },
                },
            };

            ApiResponse::new(
                Some(to_value(response).unwrap()),
                "User logged in successfully".to_owned(),
                StatusCode::OK,
            )
        }
        Err(err) => ApiResponse::err(None, err),
    };

    Json(response)
}

#[axum::debug_handler]
pub async fn get_access_token(
    State((user_service, jwt_service)): State<(UserService, JWTService)>,
    Json(request): Json<TokenRequest>,
) -> impl IntoResponse {
    let refresh_claims = match jwt_service.decode_refresh_token(&request.refresh_token) {
        Ok(claims) => claims,
        Err(_) => {
            return Json(ApiResponse {
                response_data: None,
                message: "Invalid refresh token".to_string(),
                status: StatusCode::UNAUTHORIZED.into(),
            });
        }
    };

    let response = match user_service.get_user(refresh_claims.sub.parse().unwrap()) {
        Ok(user) => {
            let new_access_token = match jwt_service.encode_access_token(&user) {
                Ok(token) => token,
                Err(_) => {
                    return Json(ApiResponse {
                        response_data: None,
                        message: "Failed to generate access token".to_string(),
                        status: StatusCode::INTERNAL_SERVER_ERROR.into(),
                    });
                }
            };

            let response = AccessTokenResponse {
                access_token: new_access_token,
                token_type: "Bearer".to_string(),
                expires_in: jwt_service.get_expiration_hours() * 3600,
                user: UserInfo {
                    id: user.id,
                    username: user.username,
                    email: user.email,
                    role: if user.is_admin {
                        "admin".to_string()
                    } else {
                        "user".to_string()
                    },
                },
            };

            ApiResponse::new(
                Some(to_value(response).unwrap()),
                "Access token generated successfully".to_string(),
                StatusCode::OK,
            )
        }
        Err(err) => ApiResponse::err(None, err),
    };

    Json(response)
}

#[axum::debug_handler]
pub async fn refresh_token(
    State((user_service, jwt_service)): State<(UserService, JWTService)>,
    Json(request): Json<TokenRequest>,
) -> impl IntoResponse {
    let refresh_claims = match jwt_service.decode_refresh_token(&request.refresh_token) {
        Ok(claims) => claims,
        Err(_) => {
            return Json(ApiResponse {
                response_data: None,
                message: "Invalid refresh token".to_string(),
                status: StatusCode::UNAUTHORIZED.into(),
            });
        }
    };

    let user = match user_service.get_user(refresh_claims.sub.parse().unwrap()) {
        Ok(user) => user,
        Err(err) => {
            return Json(ApiResponse::err(None, err));
        }
    };

    let new_access_token = match jwt_service.encode_access_token(&user) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_data: None,
                message: "Failed to generate access token".to_string(),
                status: StatusCode::INTERNAL_SERVER_ERROR.into(),
            });
        }
    };

    let new_refresh_token = match jwt_service.encode_refresh_token(&user.id.to_string()) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_data: None,
                message: "Failed to generate refresh token".to_string(),
                status: StatusCode::INTERNAL_SERVER_ERROR.into(),
            });
        }
    };

    let response = RefreshTokenResponse {
        access_token: new_access_token,
        refresh_token: new_refresh_token,
        token_type: "Bearer".to_string(),
        expires_in: jwt_service.get_expiration_hours() * 3600,
        user: UserInfo {
            id: user.id,
            username: user.username,
            email: user.email,
            role: if user.is_admin {
                "admin".to_string()
            } else {
                "user".to_string()
            },
        },
    };

    Json(ApiResponse::new(
        Some(to_value(response).unwrap()),
        "Tokens refreshed successfully".to_owned(),
        StatusCode::OK,
    ))
}
