use crate::plugins::canvas::client::CanvasClient;
use crate::plugins::canvas::config::{CanvasConfig, ConfigError};
use crate::plugins::canvas::tools::{GetCourseTool, GetCoursesTool};
use crate::server::tool_registry::ToolRegistry;

pub fn canvas_plugin_setup(tools: &mut ToolRegistry) -> Result<(), ConfigError> {
    let CanvasConfig { api_url, api_token } = CanvasConfig::from_env()?;
    let canvas_client = CanvasClient::new(api_url, api_token);

    tools
        .register(Box::new(GetCourseTool {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(GetCoursesTool { canvas_client }));

    Ok(())
}
