use app_core::UserService;
use axum::{
    Router,
    routing::{get, post},
};

use crate::{
    auth::{get_access_token, get_test_token, login, refresh_token},
    jwt::JWTService,
};

pub fn auth_routes() -> Router<(UserService, JWTService)> {
    Router::new()
        .route("/login", post(login))
        .route("/access-token", post(get_access_token))
        .route("/refresh-token", post(refresh_token))
        .route("/test-token", get(get_test_token))
}
