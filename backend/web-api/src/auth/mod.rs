use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::api_response::ApiResponse;
use crate::jwt::JWTService;

// Import necessary types from the core crate
use app_core::db::{get_db_pool, DbPool, User, CoreError};

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Deserialize)]
pub struct AccessTokenRequest {
    pub refresh_token: String,
}

#[derive(Debug, Deserialize)]
pub struct RefreshTokenRequest {
    pub refresh_token: String,
}

#[derive(Debug, Serialize)]
pub struct AuthResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserInfo,
}

#[derive(Debug, Serialize)]
pub struct AccessTokenResponse {
    pub access_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserInfo,
}

#[derive(Debug, Serialize)]
pub struct RefreshTokenResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserInfo,
}

#[derive(Debug, Serialize)]
pub struct UserInfo {
    pub id: i32,
    pub username: String,
    pub email: String,
    pub role: String,
}

pub fn create_auth_router(jwt_service: Arc<JWTService>) -> Router {
    Router::new()
        .route("/login", post(login))
        .route("/access-token", post(get_access_token))
        .route("/refresh-token", post(refresh_token))
        .route("/test-token", get(get_test_token))
        .with_state((get_db_pool, jwt_service))
}

pub async fn get_test_token(
    State((db_pool, jwt_service)): State<(Arc<DbPool>, Arc<JWTService>)>,
) -> Json<ApiResponse<AuthResponse>> {

    // Get first user for testing (in production, this should be a proper login endpoint)
    // For demo purposes, we're using the email of the first active user
    let all_users = User::get_list(&db_pool).expect("Failed to get users");
    let user = all_users.into_iter()
        .find(|u| u.is_active)
        .expect("No active users found - please create an active user first");

    // Generate tokens
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
            role: if user.is_admin { "admin".to_string() } else { "user".to_string() },
        },
    };

    ApiResponse::ok(response, "Test token generated successfully").unwrap()
}

pub async fn login(
    State((db_pool, jwt_service)): State<(Arc<app_core::DbPool>, Arc<JWTService>)>,
    Json(login_request): Json<LoginRequest>,
) -> Json<ApiResponse<AuthResponse>> {
    // Authenticate user
    let user = match User::authenticate(&login_request.email, &login_request.password, &db_pool) {
        Ok(user) => user,
        Err(CoreError::AuthenticationError(_)) => {
            return Json(ApiResponse {
                response_code: 401,
                response_message: "Invalid credentials".to_string(),
                data: (),
            });
        }
        Err(_) => {
            return Json(ApiResponse::err{
                response_code: 500,
                response_message: "Internal server error".to_string(),
            });
        }
    };

    // Generate tokens
    let access_token = match jwt_service.encode_access_token(&user) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 500,
                response_message: "Failed to generate access token".to_string(),
                data: (),
            });
        }
    };

    let refresh_token = match jwt_service.encode_refresh_token(&user.id.to_string()) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 500,
                response_message: "Failed to generate refresh token".to_string(),
                data: (),
            });
        }
    };

    let response = AuthResponse {
        access_token,
        refresh_token,
        token_type: "Bearer".to_string(),
        expires_in: jwt_service.get_expiration_hours() * 3600, // Convert hours to seconds
        user: UserInfo {
            id: user.id,
            username: user.username,
            email: user.email,
            role: if user.is_admin { "admin".to_string() } else { "user".to_string() },
        },
    };

    ApiResponse::ok(response, "Login successful").unwrap()
}

pub async fn get_access_token(
    State((db_pool, jwt_service)): State<(Arc<app_core::DbPool>, Arc<JWTService>)>,
    Json(request): Json<AccessTokenRequest>,
) -> Json<ApiResponse<AccessTokenResponse>> {
    // Decode and validate the refresh token
    let refresh_claims = match jwt_service.decode_refresh_token(&request.refresh_token) {
        Ok(claims) => claims,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 401,
                response_message: "Invalid refresh token".to_string(),
                data: (),
            });
        }
    };

    // Get the user from database using the user id from the refresh token
    let user = match User::get(refresh_claims.sub.parse().unwrap(), &db_pool) {
        Ok(user) => user,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 401,
                response_message: "User not found".to_string(),
                data: (),
            });
        }
    };

    // Generate new access token
    let new_access_token = match jwt_service.encode_access_token(&user) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 500,
                response_message: "Failed to generate access token".to_string(),
                data: (),
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
            role: if user.is_admin { "admin".to_string() } else { "user".to_string() },
        },
    };

    ApiResponse::ok(response, "Access token generated successfully").unwrap()
}

pub async fn refresh_token(
    State((db_pool, jwt_service)): State<(Arc<app_core::DbPool>, Arc<JWTService>)>,
    Json(request): Json<RefreshTokenRequest>,
) -> Json<ApiResponse<RefreshTokenResponse>> {
    // Decode and validate the refresh token
    let refresh_claims = match jwt_service.decode_refresh_token(&request.refresh_token) {
        Ok(claims) => claims,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 401,
                response_message: "Invalid refresh token".to_string(),
                data: (),
            });
        }
    };

    // Get the user from database using the user id from the refresh token
    let user = match User::get(refresh_claims.sub.parse().unwrap(), &db_pool) {
        Ok(user) => user,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 401,
                response_message: "User not found".to_string(),
                data: (),
            });
        }
    };

    // Generate new access token
    let new_access_token = match jwt_service.encode_access_token(&user) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 500,
                response_message: "Failed to generate access token".to_string(),
                data: (),
            });
        }
    };

    // Generate new refresh token
    let new_refresh_token = match jwt_service.encode_refresh_token(&user.id.to_string()) {
        Ok(token) => token,
        Err(_) => {
            return Json(ApiResponse {
                response_code: 500,
                response_message: "Failed to generate refresh token".to_string(),
                data: (),
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
            role: if user.is_admin { "admin".to_string() } else { "user".to_string() },
        },
    };

    ApiResponse::ok(response, "Tokens refreshed successfully").unwrap()
}

pub fn auth_routes(db_pool: Arc<DbPool>) -> Router {
    // Create JWT service from environment variables
    let jwt_secret = std::env::var("JWT_SECRET").expect("JWT_SECRET must be set");
    let jwt_expiration_hours = std::env::var("JWT_EXPIRATION_HOURS")
        .ok()
        .and_then(|s| s.parse().ok());
    let jwt_refresh_expiration_days = std::env::var("JWT_REFRESH_EXPIRATION_DAYS")
        .ok()
        .and_then(|s| s.parse().ok());

    let jwt_service = Arc::new(
        JWTService::new(&jwt_secret, jwt_expiration_hours, jwt_refresh_expiration_days)
            .expect("Failed to create JWT service")
    );

    create_auth_router(db_pool, jwt_service)
}
