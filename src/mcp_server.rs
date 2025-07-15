use crate::prompts;
use rmcp::{
    handler::server::tool::{Parameters, ToolRouter}, model::{
        CallToolResult, Content, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo,
    }, schemars::{self, JsonSchema}, tool, tool_handler, tool_router, Error, ServerHandler
};
use serde::{Deserialize, Serialize};
use serde_json::json;

// #[derive(JsonSchema, Deserialize)]
// pub struct CourseGenerationPromptRequest {
//     #[schemars(description = "the duration of the course")]
//     course_duration: String,
//     #[schemars(description = "the name of the course")]
//     course_name: String,
//     #[schemars(description = "a brief description of the course")]
//     course_description: String,
// }

// #[derive(JsonSchema, Deserialize)]
// pub struct CourseGenerationPromptRequest {
//     query: String,
//     // #[schemars(description = "the name of the course")]
//     // course_name: String,
//     // #[schemars(description = "a brief description of the course")]
//     // course_description: String,
// }

#[derive(JsonSchema, Deserialize)]
pub struct SearchRequest {
    #[schemars(description = "the query argument for the search tool")]
    query: String,
}

#[derive(JsonSchema, Deserialize)]
pub struct FetchRequest {
    #[schemars(description = "the id argument for the fetch tool")]
    id: String,
}

#[derive(Serialize)]
pub struct Response {
    pub id: i32,
    pub title: String,
    pub text: String,
    pub url: String,
}

#[derive(Clone)]
pub struct SparkthMCPServer {
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl SparkthMCPServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
        }
    }

    // #[tool(
    //     description = "Generates a prompt for creating a course structure based on the course name, description and duration passed as the arguments. The course should follow instructional design principles."
    // )]
    // pub fn get_course_generation_prompt(
    //     &self,
    //     #[tool(aggr)] CourseGenerationPromptRequest {
    //         course_name,
    //         course_duration,
    //         course_description,
    //     }: CourseGenerationPromptRequest,
    // ) -> Result<CallToolResult, Error> {
    //     let prompt = prompts::get_course_generation_prompt(
    //         &course_name,
    //         &course_duration,
    //         &course_description,
    //     );
    //     Ok(CallToolResult::success(vec![Content::text(prompt)]))
    // }

    #[tool(
        description = "Fetches a prompt for creating a course structure based on the course name, description and duration passed as the arguments. The course should follow instructional design principles."
    )]
    pub fn fetch(
        &self,
        Parameters(FetchRequest { id }): Parameters<FetchRequest>,
    ) -> Result<CallToolResult, Error> {
        let prompt = prompts::get_course_generation_prompt(
            "Rust for Beginners",
            "4 weeks",
            "A comprehensive course on Rust programming language.",
        );


        let response =  json!({
            "id": id,
            "title": "Rust for Beginners",
            "text": prompt,
            "url": "/",
            "metadata": None::<String>
        });

        Ok(CallToolResult::success(vec![Content::text(response.to_string())]))
    }

    #[tool(
        description = "Searches for a prompt for creating a course structure based on the course name, description and duration passed as the arguments. The course should follow instructional design principles."
    )]
    pub fn search(
        &self,
        Parameters(SearchRequest { query }): Parameters<SearchRequest>,
    ) -> Result<CallToolResult, Error> {
        let prompt = prompts::get_course_generation_prompt(
            "Rust for Beginners",
            "4 weeks",
            "A comprehensive course on Rust programming language.",
        );
        let response =  serde_json::to_string(&Response {
            id: 1,
            title: "Course generation prompt".to_string(),
            text: prompt,
            url: "/".to_string(),
        }).unwrap();

        Ok(CallToolResult::success(vec![Content::text(response)]))
    }
}

#[tool_handler]
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
