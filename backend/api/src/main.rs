use axum::{Router, routing::get};
use tokio::net::TcpListener;
use std::{env, error::Error};

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    dotenvy::dotenv()?;

    let host = env::var("HOST")?;
    let port = env::var("PORT")?;

    let app = Router::new().route("/", get(|| async { "Hello, World!" }));

    let listener = TcpListener::bind(format!("{host}:{port}"))
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();

    Ok(())
}
