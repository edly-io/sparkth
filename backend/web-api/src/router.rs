use app_core::{PluginService, UserService};
use axum::{
    Router,
    http::{HeaderValue, Method, header::CONTENT_TYPE},
};
use tower_http::cors::CorsLayer;

use crate::{auth::auth_routes, jwt::JWTService, plugins::plugin_routes};

pub async fn router() -> Router {
    let jwt_secret = std::env::var("JWT_SECRET").expect("JWT_SECRET must be set");
    let jwt_expiration_hours = std::env::var("JWT_EXPIRATION_HOURS")
        .ok()
        .and_then(|s| s.parse().ok());
    let jwt_refresh_expiration_days = std::env::var("JWT_REFRESH_EXPIRATION_DAYS")
        .ok()
        .and_then(|s| s.parse().ok());

    let jwt_service = JWTService::new(
        &jwt_secret,
        jwt_expiration_hours,
        jwt_refresh_expiration_days,
    )
    .expect("Failed to create JWT service");
    let user_service = UserService;

    let plugin_service = PluginService;

    let auth_router = auth_routes().with_state((user_service, jwt_service));
    let plugin_router = plugin_routes().with_state(plugin_service);

    let api_router = Router::new().merge(auth_router).merge(plugin_router);

    Router::new().nest("/api", api_router).layer(
        CorsLayer::new()
            .allow_origin(HeaderValue::from_static("http://localhost:3000"))
            .allow_credentials(true)
            .allow_headers([CONTENT_TYPE])
            .allow_methods([Method::GET, Method::PATCH, Method::POST, Method::DELETE]),
    )
}
