mod api_response;
mod error;
mod plugins;
mod jwt;

use axum::{
    Router,
    http::{HeaderValue, Method, header::CONTENT_TYPE},
    routing::get,
};
use std::{env, error::Error};
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use tracing_subscriber::fmt::format::FmtSpan;

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

    let app = Router::new()
        .route("/health", get(|| async { "Hello, World!" }))
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
