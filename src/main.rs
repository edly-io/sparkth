mod plugins;
mod prompts;
mod server;
mod tools;
mod utils;

use crate::server::mcp_server::SparkthMCPServer;
use clap::{Parser, ValueEnum, arg};
use rmcp::transport::sse_server::{SseServer, SseServerConfig};
use rmcp::{ServiceExt, transport::stdio};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Debug, Clone, ValueEnum)]
enum Mode {
    Sse,
    Stdio,
}

#[derive(Parser, Debug)]
struct ServerConfigArgs {
    #[arg(long, default_value_t = String::from("0.0.0.0"))]
    host: String,

    #[arg(long, default_value_t = 7727)]
    port: u16,

    #[arg(short, long, value_enum, default_value_t = Mode::Sse)]
    mode: Mode,
}

async fn run_sse_server(
    host: String,
    port: u16,
    mcp: SparkthMCPServer,
) -> Result<(), Box<dyn std::error::Error>> {
    let bind_address = format!("{host}:{port}");

    let config = SseServerConfig {
        bind: bind_address.parse()?,
        sse_path: "/".to_string(),
        post_path: "/message".to_string(),
        ct: tokio_util::sync::CancellationToken::new(),
        sse_keep_alive: None,
    };

    let server = SseServer::serve_with_config(config).await?;

    eprintln!("🚀 SSE server listening on http://{bind_address}");
    let ct = server.with_service(move || mcp.clone());
    tokio::signal::ctrl_c().await?;
    ct.cancel();

    Ok(())
}

async fn run_stdio_server(mcp: SparkthMCPServer) -> Result<(), Box<dyn std::error::Error>> {
    let service = mcp
        .serve(stdio())
        .await
        .inspect_err(|err| eprintln!("{err}"))?;

    eprintln!("🚀 Stdio server listening (waiting for messages)");
    service.waiting().await?;

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "debug".to_string().into()),
        )
        .with(tracing_subscriber::fmt::layer().with_writer(std::io::stderr))
        .init();

    let args = ServerConfigArgs::parse();
    let sparkth_mcp = SparkthMCPServer::new();

    match args.mode {
        Mode::Sse => run_sse_server(args.host, args.port, sparkth_mcp).await?,
        Mode::Stdio => run_stdio_server(sparkth_mcp).await?,
    }

    Ok(())
}
