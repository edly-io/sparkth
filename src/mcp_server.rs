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
    course_duration: String,
    #[schemars(description = "the name of the course")]
    course_name: String,
    #[schemars(description = "a brief description of the course")]
    course_description: String,
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

#[derive(Clone)]
pub struct SparkthMCPServer {
    canvas_client: CanvasClient,
}

#[tool(tool_box)]
impl SparkthMCPServer {
    pub fn new(api_url: String, api_token: String) -> Self {
        Self {
            canvas_client: CanvasClient::new(api_url, api_token),
        }
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

    #[tool(description = "Returns a list of all available courses in the Canvas instance.")]
    pub async fn get_courses(&self) -> Result<CallToolResult, Error> {
        match self.canvas_client.get_courses(None).await {
            Ok(courses) => Ok(CallToolResult::success(vec![Content::text(
                serde_json::to_string(&courses).unwrap(),
            )])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(format!(
                "Error fetching courses: {}",
                e
            ))])),
        }
    }

    #[tool(description = "Returns the couse based on the course id")]
    pub async fn get_course(
        &self,
        #[tool(aggr)] CourseRetrievalRequest { course_id }: CourseRetrievalRequest,
    ) -> Result<CallToolResult, Error> {
        match self.canvas_client.get_course(&course_id).await {
            Ok(courses) => Ok(CallToolResult::success(vec![Content::text(
                serde_json::to_string(&courses).unwrap(),
            )])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(format!(
                "Error fetching the course: {}",
                e
            ))])),
        }
    }

    #[tool(description = "")]
    pub async fn create_course(
        &self,
        #[tool(aggr)] CourseCreationRequest {
            account_id,
            name,
            course_code,
            sis_course_id,
        }: CourseCreationRequest,
    ) -> Result<CallToolResult, Error> {
        match self
            .canvas_client
            .create_course(account_id, name, course_code, sis_course_id)
            .await
        {
            Ok(course) => Ok(CallToolResult::success(vec![Content::text(
                serde_json::to_string(&course).unwrap(),
            )])),
            Err(e) => Ok(CallToolResult::error(vec![Content::text(format!(
                "Error creating the course: {}",
                e
            ))])),
        }
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
