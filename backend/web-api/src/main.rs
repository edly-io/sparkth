mod api_response;
mod auth;
mod jwt;
mod middleware;
mod plugins;
mod router;

use std::{env, error::Error};
use tokio::net::TcpListener;
use tracing_subscriber::fmt::format::FmtSpan;

use crate::router::router;

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

    let app = router().await;

    let listener = TcpListener::bind(format!("{host}:{port}")).await.unwrap();
    axum::serve(listener, app).await.unwrap();

    Ok(())
}
