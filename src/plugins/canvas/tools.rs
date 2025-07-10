use crate::{
    plugins::canvas::{client::CanvasClient, types::GetCourseRequest},
    server::tool::{Tool, ToolError},
};
use async_trait::async_trait;
use rmcp::model::{CallToolResult, Content};
use serde_json::Value;

pub struct GetCourseTool {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetCourseTool {
    fn name(&self) -> &str {
        "get_course"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let args_json = args.ok_or(ToolError::MissingArgs {
            name: self.name().into(),
            args: "course_id".into(),
        })?;

        let args: GetCourseRequest =
            serde_json::from_value(args_json).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id".into(),
            })?;

        match self.canvas_client.get_course(&args.course_id).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => Ok(CallToolResult::error(vec![Content::text(format!(
                "Error fetching the courses: {:?}",
                err
            ))])),
        }
    }
}

pub struct GetCoursesTool {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetCoursesTool {
    fn name(&self) -> &str {
        "get_courses"
    }

    async fn call(&self, _args: Option<Value>) -> Result<CallToolResult, ToolError> {
        match self.canvas_client.get_courses(None).await {
            Ok(result) => {
                let courses: Vec<String> = result
                    .into_iter()
                    .map(|course| course.to_string())
                    .collect();
                Ok(CallToolResult::success(vec![Content::text(
                    courses.join(","),
                )]))
            }
            Err(err) => Ok(CallToolResult::error(vec![Content::text(format!(
                "Error fetching the courses: {:?}",
                err
            ))])),
        }
    }
}
