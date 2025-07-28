use crate::{
    plugins::canvas::client::CanvasClient,
    server::{
        tool_trait::{Tool, ToolError}, types::{CourseParams, CoursePayload, EnrollmentPayload, ListPagesPayload, ListUsersParams, ModuleItemParams, ModuleItemPayload, ModuleParams, ModulePayload, PageParams, PagePayload, QuestionParams, QuestionPayload, QuizParams, QuizPayload, UpdateModuleItemPayload, UpdateModulePayload, UpdatePagePayload, UpdateQuestionPayload, UpdateQuizPayload, UserPayload},
        
    },
};
use async_trait::async_trait;
use rmcp::model::{CallToolResult, Content, ErrorCode};
use serde_json::{Value, from_value};

fn parse_args(
    tool_name: &str,
    args: Option<Value>,
    expected_args: &str,
) -> Result<Value, ToolError> {
    let args_value = match args {
        Some(Value::String(s)) => {
            serde_json::from_str::<Value>(&s).map_err(|_| ToolError::InvalidArgs {
                name: tool_name.to_string(),
                args: expected_args.to_string(),
            })?
        }
        Some(val) => val,
        None => {
            return Err(ToolError::MissingArgs {
                name: tool_name.to_string(),
                args: expected_args.to_string(),
            });
        }
    };

    Ok(args_value)
}

pub struct GetCourse {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetCourse {
    fn name(&self) -> &str {
        "get_course"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String")?;
        let get_course_args: CourseParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id".into(),
            })?;

        match self
            .canvas_client
            .get_course(get_course_args.course_id)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!(
                    "Error fetching course {}: {:?}",
                    get_course_args.course_id, err
                );
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct GetCourses {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetCourses {
    fn name(&self) -> &str {
        "get_courses"
    }

    async fn call(&self, _args: Option<Value>) -> Result<CallToolResult, ToolError> {
        match self.canvas_client.get_courses().await {
            Ok(result) => {
                let courses: Vec<String> = result
                    .into_iter()
                    .map(|course| course.to_string())
                    .collect();
                Ok(CallToolResult::success(vec![Content::text(
                    courses.join(","),
                )]))
            }
            Err(err) => {
                let message = format!("Error fetching the courses: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreateCourse {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreateCourse {
    fn name(&self) -> &str {
        "create_course"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "account_id: String, name: String")?;

        let create_course_args: CoursePayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "account_id: String, name: String".into(),
            })?;

        match self.canvas_client.create_course(create_course_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating a new course: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct ListModules {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for ListModules {
    fn name(&self) -> &str {
        "list_modules"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String")?;

        let course_args: CourseParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String".into(),
            })?;

        match self.canvas_client.list_modules(course_args).await {
            Ok(result) => {
                let modules: Vec<String> = result
                    .into_iter()
                    .map(|module| module.to_string())
                    .collect();

                Ok(CallToolResult::success(vec![Content::text(
                    modules.join(","),
                )]))
            }
            Err(err) => {
                let message = format!("Error listing the modules: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct GetModule {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetModule {
    fn name(&self) -> &str {
        "get_module"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, module_id: String")?;

        let get_module_args: ModuleParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String".into(),
            })?;

        match self.canvas_client.get_module(get_module_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error fetching the requested module: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreateModule {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreateModule {
    fn name(&self) -> &str {
        "create_module"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, name: String")?;

        let create_module_args: ModulePayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, name: String".into(),
            })?;

        match self.canvas_client.create_module(create_module_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating a new module: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct UpdateModule {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for UpdateModule {
    fn name(&self) -> &str {
        "update_module"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, module_id: String")?;

        let update_module_args: UpdateModulePayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String".into(),
            })?;

        match self.canvas_client.update_module(update_module_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error updating the module: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct DeleteModule {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for DeleteModule {
    fn name(&self) -> &str {
        "delete_module"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, module_id: String")?;

        let delete_module_args: ModuleParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String".into(),
            })?;

        match self.canvas_client.delete_module(delete_module_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error deleting the module: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct ListModuleItems {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for ListModuleItems {
    fn name(&self) -> &str {
        "list_module_items"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, module_id: String")?;

        let list_mod_items_args: ModuleParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String".into(),
            })?;

        match self
            .canvas_client
            .list_module_items(list_mod_items_args)
            .await
        {
            Ok(result) => {
                let items: Vec<String> = result.into_iter().map(|item| item.to_string()).collect();
                Ok(CallToolResult::success(vec![Content::text(
                    items.join("\n"),
                )]))
            }
            Err(err) => {
                let message = format!("Error listing the modules: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct GetModuleItem {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetModuleItem {
    fn name(&self) -> &str {
        "get_module_item"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, module_id: String, item_id: String",
        )?;

        let get_item_args: ModuleItemParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String, item_id: String".into(),
            })?;

        match self.canvas_client.get_module_item(get_item_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error getting the module item: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreateModuleItem {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreateModuleItem {
    fn name(&self) -> &str {
        "create_module_item"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, module_id: String, item_type: String, title: String",
        )?;

        let create_item_args: ModuleItemPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String, item_type: String, title: String"
                    .into(),
            })?;

        match self
            .canvas_client
            .create_module_item(create_item_args)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating the module item: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct UpdateModuleItem {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for UpdateModuleItem {
    fn name(&self) -> &str {
        "update_module_item"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, module_id: String, item_id: String",
        )?;

        let update_module_item_args: UpdateModuleItemPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String, item_id: String".into(),
            })?;

        match self
            .canvas_client
            .update_module_item(update_module_item_args)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error updating the module item: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct DeleteModuleItem {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for DeleteModuleItem {
    fn name(&self) -> &str {
        "delete_module_item"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, module_id: String, item_id: String",
        )?;

        let delete_module_item_args: ModuleItemParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String, item_id: String".into(),
            })?;

        match self
            .canvas_client
            .delete_module_item(delete_module_item_args)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error deleting the module item: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct ListPages {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for ListPages {
    fn name(&self) -> &str {
        "list_pages"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, search_term: Option<String>",
        )?;

        let list_pages_args: ListPagesPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, search_term: Option<String>".into(),
            })?;

        match self.canvas_client.list_pages(list_pages_args).await {
            Ok(result) => {
                let items: Vec<String> = result.into_iter().map(|item| item.to_string()).collect();
                Ok(CallToolResult::success(vec![Content::text(
                    items.join("\n"),
                )]))
            }
            Err(err) => {
                let message = format!("Error listing the pages: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct GetPage {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetPage {
    fn name(&self) -> &str {
        "get_page"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, page_url: String")?;

        let get_page: PageParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, page_url: String".into(),
            })?;

        match self.canvas_client.get_page(get_page).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error getting the requested page: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreatePage {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreatePage {
    fn name(&self) -> &str {
        "create_page"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, title: String, body: String",
        )?;

        let create_page_args: PagePayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, title: String, body: String".into(),
            })?;

        match self.canvas_client.create_page(create_page_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating the page: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct UpdatePage {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for UpdatePage {
    fn name(&self) -> &str {
        "update_page"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, page_url: String")?;

        let update_page_args: UpdatePagePayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, page_url: String".into(),
            })?;

        match self.canvas_client.update_page(update_page_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error updating the module item: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct DeletePage {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for DeletePage {
    fn name(&self) -> &str {
        "delete_page"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, page_url: String")?;

        let delete_page_args: PageParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, page_url: String".into(),
            })?;

        match self.canvas_client.delete_page(delete_page_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error deleting the page: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

// pub struct AddPageToModule {
//     pub canvas_client: CanvasClient,
// }

// #[async_trait]
// impl Tool for AddPageToModule {
//     fn name(&self) -> &str {
//         "add_page_to_module"
//     }

//     async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
//         let parsed_args = parse_args(
//             self.name(),
//             args,
//             "course_id: String, module_id: String, page_url: String",
//         )?;

//         let add_page_args: AddPageRequest =
//             from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
//                 name: self.name().into(),
//                 args: "course_id: String, module_id: String, page_url: String".into(),
//             })?;

//         match self.canvas_client.add_page_to_module(add_page_args).await {
//             Ok(result) => Ok(CallToolResult::success(vec![Content::text(
//                 result.to_string(),
//             )])),
//             Err(err) => {
//                 let message = format!("Error adding page to module: {:?}", err);
//                 Err(ToolError::InternalError {
//                     error_code: ErrorCode::INTERNAL_ERROR,
//                     message,
//                 })
//             }
//         }
//     }
// }

pub struct ListQuizzes {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for ListQuizzes {
    fn name(&self) -> &str {
        "list_quizzes"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String")?;

        let list_quizzes_args: CourseParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String".into(),
            })?;

        match self.canvas_client.list_quizzes(list_quizzes_args).await {
            Ok(result) => {
                let items: Vec<String> = result.into_iter().map(|item| item.to_string()).collect();
                Ok(CallToolResult::success(vec![Content::text(
                    items.join("\n"),
                )]))
            }
            Err(err) => {
                let message = format!("Error listing the quizzes: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct GetQuiz {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetQuiz {
    fn name(&self) -> &str {
        "get_quiz"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, quiz_id: String")?;

        let get_quiz: QuizParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String".into(),
            })?;

        match self.canvas_client.get_quiz(get_quiz).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error getting the requested quiz: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreateQuiz {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreateQuiz {
    fn name(&self) -> &str {
        "create_quiz"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, title: String, description: String, quiz_type: String",
        )?;

        let create_quiz_args: QuizPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, title: String, description: String, quiz_type: String"
                    .into(),
            })?;

        match self.canvas_client.create_quiz(create_quiz_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating the quiz: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct UpdateQuiz {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for UpdateQuiz {
    fn name(&self) -> &str {
        "update_quiz"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, quiz_id: String")?;

        let update_quiz_args: UpdateQuizPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String".into(),
            })?;

        match self.canvas_client.update_quiz(update_quiz_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error updating the quiz: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct DeleteQuiz {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for DeleteQuiz {
    fn name(&self) -> &str {
        "delete_quiz"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, quiz_id: String")?;

        let delete_quiz_args: QuizParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String".into(),
            })?;

        match self.canvas_client.delete_quiz(delete_quiz_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error deleting the quiz: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

// pub struct AddQuizToModule {
//     pub canvas_client: CanvasClient,
// }

// #[async_trait]
// impl Tool for AddQuizToModule {
//     fn name(&self) -> &str {
//         "add_quiz_to_module"
//     }

//     async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
//         let parsed_args = parse_args(
//             self.name(),
//             args,
//             "course_id: String, module_id: String, quiz_id: String",
//         )?;

//         let add_quiz_args: AddQuizRequest =
//             from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
//                 name: self.name().into(),
//                 args: "course_id: String, module_id: String, quiz_id: String".into(),
//             })?;

//         match self.canvas_client.add_quiz_to_module(add_quiz_args).await {
//             Ok(result) => Ok(CallToolResult::success(vec![Content::text(
//                 result.to_string(),
//             )])),
//             Err(err) => {
//                 let message = format!("Error adding quiz to module: {:?}", err);
//                 Err(ToolError::InternalError {
//                     error_code: ErrorCode::INTERNAL_ERROR,
//                     message,
//                 })
//             }
//         }
//     }
// }

pub struct ListQuestions {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for ListQuestions {
    fn name(&self) -> &str {
        "list_questions"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "course_id: String, quiz_id: String")?;

        let list_questions_args: QuizParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String".into(),
            })?;

        match self.canvas_client.list_questions(list_questions_args).await {
            Ok(result) => {
                let items: Vec<String> = result.into_iter().map(|item| item.to_string()).collect();
                Ok(CallToolResult::success(vec![Content::text(
                    items.join("\n"),
                )]))
            }
            Err(err) => {
                let message = format!("Error listing the questions: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct GetQuestion {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for GetQuestion {
    fn name(&self) -> &str {
        "get_question"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, quiz_id: String, question_id: String",
        )?;

        let get_question: QuestionParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String, question_id: String".into(),
            })?;

        match self.canvas_client.get_question(get_question).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error getting the requested question: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreateQuestion {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreateQuestion {
    fn name(&self) -> &str {
        "create_question"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, title: String, description: String, quiz_type: String",
        )?;

        let create_question_args: QuestionPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String, name: String, text: String, answers: Vec<Answer>. Answer type has {answer_text: String, answer_weight: u8}. Weight is 0 for incorrect answers, 100 for the correct one.".into(),
            })?;

        match self
            .canvas_client
            .create_question(create_question_args)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating the question: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct UpdateQuestion {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for UpdateQuestion {
    fn name(&self) -> &str {
        "update_question"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, quiz_id: String, question_id: String",
        )?;

        let update_question_args: UpdateQuestionPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String, question_id: String".into(),
            })?;

        match self
            .canvas_client
            .update_question(update_question_args)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error updating the question: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct DeleteQuestion {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for DeleteQuestion {
    fn name(&self) -> &str {
        "delete_question"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, quiz_id: String, question_id: String",
        )?;

        let delete_question_args: QuestionParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, quiz_id: String, question_id: String".into(),
            })?;

        match self
            .canvas_client
            .delete_question(delete_question_args)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error deleting the question: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct ListUsers {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for ListUsers {
    fn name(&self) -> &str {
        "list_users"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(self.name(), args, "account_id: String")?;

        let list_users_args: ListUsersParams =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "account_id: String".into(),
            })?;

        match self.canvas_client.list_users(list_users_args).await {
            Ok(result) => {
                let items: Vec<String> = result.into_iter().map(|item| item.to_string()).collect();
                Ok(CallToolResult::success(vec![Content::text(
                    items.join("\n"),
                )]))
            }
            Err(err) => {
                let message = format!("Error listing the users: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct CreateUser {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for CreateUser {
    fn name(&self) -> &str {
        "create_user"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "account_id: String, name: String, unique_id: String, short_name: Option<String>, sortable_name: Option<String>, send_confirmation: Option<bool>, communication_type: Option<String>, communication_address: Option<String>",
        )?;

        let create_user: UserPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "account_id: String, name: String, unique_id: String, short_name: Option<String>, sortable_name: Option<String>, send_confirmation: Option<bool>, communication_type: Option<String>, communication_address: Option<String>".into(),
            })?;

        match self
            .canvas_client
            .create_user(create_user)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error creating the user: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}

pub struct EnrollUser {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for EnrollUser {
    fn name(&self) -> &str {
        "enroll_user"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, user_id: String, enrollment_type: EnrollmentType {StudentEnrollment, TeacherEnrollment, TaEnrollment, ObserverEnrollment, DesignerEnrollment}, enrollment_state: {active, inactive, invited}",
        )?;

        let enroll_user: EnrollmentPayload =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, user_id: String, enrollment_type: EnrollmentType {StudentEnrollment, TeacherEnrollment, TaEnrollment, ObserverEnrollment, DesignerEnrollment}, enrollment_state: {active, inactive, invited}".into(),
            })?;

        match self
            .canvas_client
            .enroll_user(enroll_user)
            .await
        {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error enrolling the user: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}
