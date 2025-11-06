use rmcp::{
    ErrorData, ServerHandler,
    handler::server::{tool::ToolRouter, wrapper::Parameters},
    model::{
        CallToolResult, Content, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo,
    },
    schemars::JsonSchema,
    tool, tool_handler, tool_router,
};
use serde::Deserialize;
use std::sync::Arc;

use crate::{
    plugin::{PluginRegistry, error::PluginError},
    prompts,
};

#[derive(JsonSchema, Deserialize)]
pub struct CourseGenerationPromptRequest {
    #[schemars(description = "The name of the course")]
    pub course_name: String,
    #[schemars(description = "A brief description of the course")]
    pub course_description: String,
}

#[derive(Clone)]
pub struct SparkthMCPServer {
    pub tool_router: ToolRouter<Self>,
    pub plugin_registry: Arc<PluginRegistry>,
}

#[tool_router]
impl SparkthMCPServer {
    pub fn new() -> Result<Self, PluginError> {
        let plugin_registry = PluginRegistry::new();
        let tool_router = ToolRouter::new()
            + SparkthMCPServer::tool_router()
            + SparkthMCPServer::canvas_tools_router()
            + SparkthMCPServer::openedx_tools_router();

        Ok(Self {
            tool_router,
            plugin_registry: plugin_registry.into(),
        })
    }

    #[tool(description = "Generates a prompt for creating a course. 
Figure out the course name and description from the context and information.
Seek clarification whenever user responses are unclear or incomplete.")]
    pub fn get_course_generation_prompt(
        &self,
        Parameters(CourseGenerationPromptRequest {
            course_name,
            course_description,
        }): Parameters<CourseGenerationPromptRequest>,
    ) -> Result<CallToolResult, ErrorData> {
        let prompt = prompts::get_course_generation_prompt(&course_name, &course_description);
        Ok(CallToolResult::success(vec![Content::text(prompt)]))
    }

    #[tool(description = "list all the available tools.")]
    pub fn list_tools(&self) -> Result<CallToolResult, ErrorData> {
        let tools: Vec<String> = self
            .tool_router
            .list_all()
            .into_iter()
            .map(|tool| tool.name.to_string())
            .collect();
        Ok(CallToolResult::success(vec![Content::text(
            tools.join("\n"),
        )]))
    }
}

#[tool_handler]
impl ServerHandler for SparkthMCPServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation::from_build_env(),
            instructions: Some(format!(
                "This server provides the following tools:\n{:?}.",
                self.list_tools()
            )),
        }
    }
}
