use std::sync::Arc;

use crate::{prompts, server::tool_registry::ToolRegistry};
use rmcp::{
    Error, ServerHandler,
    handler::server::tool::{Parameters, ToolRouter},
    model::{
        CallToolResult, Content, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo,
    },
    schemars::{self, JsonSchema},
    tool, tool_handler, tool_router,
};
use serde::Deserialize;
use serde_json::Value;

#[derive(JsonSchema, Deserialize)]
pub struct CourseGenerationPromptRequest {
    #[schemars(description = "the duration of the course")]
    pub course_duration: String,
    #[schemars(description = "the name of the course")]
    pub course_name: String,
    #[schemars(description = "a brief description of the course")]
    pub course_description: String,
}

#[derive(JsonSchema, Deserialize)]
pub struct DispatchRequest {
    #[schemars(description = "the name of the tool to be dispatched")]
    tool_name: String,
    #[schemars(description = "the args to be passed to the tool")]
    args: Option<Value>,
}

#[derive(Clone)]
pub struct SparkthMCPServer {
    tool_registry: Arc<ToolRegistry>,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl SparkthMCPServer {
    pub fn new(registry: ToolRegistry) -> Self {
        Self {
            tool_registry: Arc::new(registry),
            tool_router: Self::tool_router(),
        }
    }

    #[tool(description = "call a tool by name.")]
    pub async fn dispatch_tool(
        &self,
        Parameters(DispatchRequest { tool_name, args }): Parameters<DispatchRequest>,
    ) -> Result<CallToolResult, Error> {
        match self.tool_registry.call(&tool_name, args).await {
            Some(result) => match result {
                Ok(tool_result) => Ok(tool_result),
                Err(e) => {
                    let msg = format!("Error while calling tool '{}': {}", tool_name, e);
                    Ok(CallToolResult::success(vec![Content::text(msg)]))
                }
            },
            None => {
                let msg = format!("Tool '{}' not found.", tool_name);
                Ok(CallToolResult::success(vec![Content::text(msg)]))
            }
        }
    }

    #[tool(
        description = "Generates a prompt for creating a course structure based on the course name, description and duration passed as the arguments. The course should follow instructional design principles."
    )]
    pub fn get_course_generation_prompt(
        &self,
        Parameters(CourseGenerationPromptRequest {
            course_name,
            course_duration,
            course_description,
        }): Parameters<CourseGenerationPromptRequest>,
    ) -> Result<CallToolResult, Error> {
        let prompt = prompts::get_course_generation_prompt(
            &course_name,
            &course_duration,
            &course_description,
        );
        Ok(CallToolResult::success(vec![Content::text(prompt)]))
    }

    #[tool(description = "list all the available tools.")]
    pub fn list_tools(&self) -> Result<CallToolResult, Error> {
        let tool_list = self.tool_registry.list_tools().join(", ");
        Ok(CallToolResult::success(vec![Content::text(tool_list)]))
    }
}

#[tool_handler]
impl ServerHandler for SparkthMCPServer {
    fn get_info(&self) -> ServerInfo {
        let tool_list = self.tool_registry.list_tools();

        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation::from_build_env(),
            instructions: Some(format!("This server provides tools: {:?}.", tool_list)),
        }
    }
}
