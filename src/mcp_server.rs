use crate::prompts;
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
    course_duration: String,
    #[schemars(description = "the name of the course")]
    course_name: String,
    #[schemars(description = "a brief description of the course")]
    course_description: String,
}

#[derive(Clone)]
pub struct SparkthMCPServer;
#[tool(tool_box)]
impl SparkthMCPServer {
    pub fn new() -> Self {
        Self {}
    }

    #[tool(
        description = "Generates a prompt for creating a course structure based on the course name, description and duration passed as the arguments. The course should follow instructional design principles."
    )]
    pub fn get_course_generation_prompt(
        &self,
        #[tool(aggr)] CourseGenerationPromptRequest {
            course_name,
            course_duration,
            course_description,
        }: CourseGenerationPromptRequest,
    ) -> Result<CallToolResult, Error> {
        let prompt = prompts::get_course_generation_prompt(
            &course_name,
            &course_duration,
            &course_description,
        );
        Ok(CallToolResult::success(vec![Content::text(prompt)]))
    }
}

#[tool(tool_box)]
impl ServerHandler for SparkthMCPServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation::from_build_env(),
            instructions: Some(
                "This server provides a tool to generate a prompt for creating a course structure based on the provided course name and duration."
                    .to_string(),
            ),
        }
    }
}
