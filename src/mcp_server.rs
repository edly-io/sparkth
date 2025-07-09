use std::{collections::HashMap, sync::Arc};

use crate::{canvas::client::CanvasClient, prompts};
use rmcp::{
    Error, ServerHandler,
    model::{
        CallToolResult, Content, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo,
    },
    schemars::{self, JsonSchema},
    tool,
};
use serde::Deserialize;

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
pub struct CourseRetrievalRequest {
    #[schemars(description = "the id of the course")]
    course_id: String,
}

#[derive(JsonSchema, Deserialize)]
pub struct CourseCreationRequest {
    #[schemars(description = "the id of the account to create the course in")]
    account_id: String,
    #[schemars(description = "the name of the course")]
    name: String,
    #[schemars(description = "the course code")]
    course_code: Option<String>,
    #[schemars(description = "the SIS course ID")]
    sis_course_id: Option<String>,
}

pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    fn call(&self) -> Result<CallToolResult, Error>;
}


pub struct ToolRegistry {
    tools: HashMap<String, Box<dyn Tool>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
        }
    }

    pub fn register(&mut self, tool: Box<dyn Tool>) {
        self.tools.insert(tool.name().to_string(), tool);
    }

    pub fn list_tools(&self) -> Vec<String> {
        self.tools.keys().cloned().collect()
    }

    pub fn call(&self, name: &str) -> Option<Result<CallToolResult, Error>> {
        self.tools.get(name).map(|t| t.call())
    }
}

pub struct GreetTool;

impl Tool for GreetTool {
    fn name(&self) -> &str {
        "greet"
    }

    fn description(&self) -> &str {
        "Greets the user warmly."
    }

    fn call(&self) -> Result<CallToolResult, Error> {
        Ok(CallToolResult::success(vec![Content::text(
            "Hello from the greet tool!".to_string(),
        )]))
    }
}

pub struct GoodbyeTool;

impl Tool for GoodbyeTool {
    fn name(&self) -> &str {
        "goodbye"
    }

    fn description(&self) -> &str {
        "say goodbye to the user."
    }

    fn call(&self) -> Result<CallToolResult, Error> {
        Ok(CallToolResult::success(vec![Content::text(
            "Goodbye from the greet tool!".to_string(),
        )]))
    }
}

#[derive(Clone)]
pub struct SparkthMCPServer {
    tool_registry: Arc<ToolRegistry>,
}

#[tool(tool_box)]
impl SparkthMCPServer {
    pub fn new_with_registry(registry: ToolRegistry) -> Self {
        Self {
            tool_registry: Arc::new(registry),
        }
    }

    #[tool(
        description = "call a tool by name."
    )]
    pub fn dispatch_tool(
        &self,
        #[tool(aggr)] tool_name: String,
    ) -> Result<CallToolResult, Error> {
        match self.tool_registry.call(&tool_name) {
            Some(result) => result,
            None => Ok(CallToolResult::success(vec![Content::text(
                format!("Tool '{}' not found.", tool_name),
            )])),
        }
    }



}




// #[derive(Clone)]
// pub struct SparkthMCPServer;

// #[tool(tool_box)]
// impl SparkthMCPServer {
//     pub fn new() -> Self {
//         Self { }
//     }

//     #[tool(
//         description = "Generates a prompt for creating a course structure based on the course name, description and duration passed as the arguments. The course should follow instructional design principles."
//     )]
//     pub fn get_course_generation_prompt(
//         &self,
//         #[tool(aggr)] CourseGenerationPromptRequest {
//             course_name,
//             course_duration,
//             course_description,
//         }: CourseGenerationPromptRequest,
//     ) -> Result<CallToolResult, Error> {

//         let prompt = prompts::get_course_generation_prompt(
//             &course_name,
//             &course_duration,
//             &course_description,
//         );
//         Ok(CallToolResult::success(vec![Content::text(prompt)]))
//     }
// }

#[tool(tool_box)]
// impl ServerHandler for SparkthMCPServer {
//     fn get_info(&self) -> ServerInfo {
//         ServerInfo {
//             protocol_version: ProtocolVersion::V_2024_11_05,
//             capabilities: ServerCapabilities::builder().enable_tools().build(),
//             server_info: Implementation::from_build_env(),
//             instructions: Some(
//                 "This server provides a tool to generate a prompt for creating a course structure based on the provided course name and duration."
//                     .to_string(),
//             ),
//         }
//     }
// }
impl ServerHandler for SparkthMCPServer {
    fn get_info(&self) -> ServerInfo {
        let tool_list = self
            .tool_registry
            .list_tools()
            .join(", ");

        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation::from_build_env(),
            instructions: Some(format!(
                "This server provides tools: {}.",
                tool_list
            )),
        }
    }
}

