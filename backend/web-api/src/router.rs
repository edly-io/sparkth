use std::env;

use app_core::{PluginService, UserService};
use axum::{
    Router,
    http::{HeaderValue, Method, header::CONTENT_TYPE},
    middleware::from_fn_with_state,
};
use tower_http::cors::CorsLayer;

use crate::{
    auth::auth_routes, jwt::init_jwt_service, middleware::inject_jwt_user, plugins::plugin_routes,
};

pub async fn router() -> Router {
    let secret = env::var("JWT_SECRET").expect("JWT_SECRET must be set");

    let jwt_service = init_jwt_service(&secret);
    let user_service = UserService;
    let plugin_service = PluginService;

    let auth_router = auth_routes().with_state((user_service, jwt_service));
    let plugin_router = plugin_routes().with_state(plugin_service);

    let api_router = Router::new()
        .merge(plugin_router)
        .layer(from_fn_with_state(secret.clone(), inject_jwt_user))
        .with_state(secret)
        .merge(auth_router);

    Router::new().nest("/api", api_router).layer(
        CorsLayer::new()
            .allow_origin(HeaderValue::from_static("http://localhost:3000"))
            .allow_credentials(true)
            .allow_headers([CONTENT_TYPE])
            .allow_methods([Method::GET, Method::PATCH, Method::POST, Method::DELETE]),
    )
}
