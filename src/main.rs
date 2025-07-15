use clap::Parser;
use rmcp::transport::{sse_server::SseServerConfig, SseServer};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::mcp_server::SparkthMCPServer;

mod mcp_server;
mod prompts;

#[derive(Parser, Debug)]
struct ServerConfigArgs {
    #[arg(long, default_value_t = String::from("0.0.0.0"))]
    host: String,

    #[arg(long, default_value_t = 7727)]
    port: u16,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = ServerConfigArgs::parse();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "debug".to_string().into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let bind_address = format!("{}:{}", args.host, args.port);

    let config = SseServerConfig {
        bind: bind_address.parse()?,
        sse_path: "/".to_string(),
        post_path: "/message".to_string(),
        ct: tokio_util::sync::CancellationToken::new(),
        sse_keep_alive: None
    };

    let ct = SseServer::serve_with_config(config)
        .await?
        .with_service(SparkthMCPServer::new);
    tokio::signal::ctrl_c().await?;
    ct.cancel();

    Ok(())
}
