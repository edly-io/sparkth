use app_core::PluginService;
use axum::{
    Router,
    http::{HeaderValue, Method, header::CONTENT_TYPE},
};
use tower_http::cors::CorsLayer;

use crate::plugins::plugin_routes;

pub async fn router() -> Router {
    let plugin_service = PluginService;

    let plugin_router = plugin_routes().with_state(plugin_service);

    let api_router = Router::new().merge(plugin_router);

    Router::new().nest("/api", api_router).layer(
        CorsLayer::new()
            .allow_origin(HeaderValue::from_static("http://localhost:3000"))
            .allow_credentials(true)
            .allow_headers([CONTENT_TYPE])
            .allow_methods([Method::GET, Method::PATCH, Method::POST, Method::DELETE]),
    )
}
