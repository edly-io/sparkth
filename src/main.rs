use rmcp::{ServiceExt, transport::stdio};

use crate::mcp_server::SparkthMCPServer;

mod mcp_server;
mod prompts;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let service = SparkthMCPServer::new()
        .serve(stdio())
        .await
        .inspect_err(|err| println!("{err}"))?;

    service.waiting().await?;
    Ok(())
}
