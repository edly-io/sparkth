mod filters;
mod plugins;
mod prompts;
mod server;

use crate::plugins::canvas::canvas_plugin::canvas_plugin_setup;
use crate::server::mcp_server::SparkthMCPServer;
use crate::server::tool_registry::ToolRegistry;
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

async fn run_sse_server(host: String, port: u16, tools_registry: ToolRegistry) -> Result<(), Box<dyn std::error::Error>> {
    let bind_address = format!("{}:{}", host, port);

    let config = SseServerConfig {
        bind: bind_address.parse()?,
        sse_path: "/".to_string(),
        post_path: "/message".to_string(),
        ct: tokio_util::sync::CancellationToken::new(),
        sse_keep_alive: None,
    };

    let sparkth_mcp = SparkthMCPServer::new(tools_registry);

    let ct = SseServer::serve_with_config(config)
        .await?
        .with_service(move || sparkth_mcp.clone());
    tokio::signal::ctrl_c().await?;
    ct.cancel();

    Ok(())
}

async fn run_stdio_server(tools_registry: ToolRegistry) -> Result<(), Box<dyn std::error::Error>> {
    let service = SparkthMCPServer::new(tools_registry)
        .serve(stdio())
        .await
        .inspect_err(|err| println!("{err}"))?;

    service.waiting().await?;

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut registry = ToolRegistry::new();
    canvas_plugin_setup(&mut registry)?;
    
    let args = ServerConfigArgs::parse();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "debug".to_string().into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    match args.mode {
        Mode::Sse => run_sse_server(args.host, args.port, registry).await?,
        Mode::Stdio => run_stdio_server(registry).await?,
    }

    Ok(())
}
