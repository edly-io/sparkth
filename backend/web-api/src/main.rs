mod api_response;
mod auth;
mod error;
mod jwt;
mod plugins;

use axum::{
    Router,
    http::{HeaderValue, Method, header::CONTENT_TYPE},
    routing::get,
};
use std::{env, error::Error};
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use tracing_subscriber::fmt::format::FmtSpan;
use app_core::db::{get_db_pool, User, CoreError};
pub fn setup_tracing() {
    tracing_subscriber::fmt()
        .with_timer(tracing_subscriber::fmt::time::UtcTime::rfc_3339())
        .with_target(true)
        .with_span_events(FmtSpan::CLOSE)
        .with_level(true)
        .with_line_number(true)
        .init();
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    dotenvy::dotenv()?;
    setup_tracing();

    let host = env::var("HOST")?;
    let port = env::var("PORT")?;

    // Create database connection pool
    let database_url = env::var("DATABASE_URL").expect("DATABASE_URL must be set");
    let db_pool = get_db_pool();
    let app = Router::new()
        .route("/health", get(|| async { "Hello, World!" }))
        .nest("/auth", auth::auth_routes(std::sync::Arc::new(db_pool.clone())))
        .layer(
            CorsLayer::new()
                .allow_origin(HeaderValue::from_static("http://localhost:3000"))
                .allow_credentials(true)
                .allow_headers([CONTENT_TYPE])
                .allow_methods([Method::GET, Method::PATCH, Method::POST, Method::DELETE]),
        );

    let listener = TcpListener::bind(format!("{host}:{port}")).await.unwrap();
    axum::serve(listener, app).await.unwrap();

    Ok(())
}
