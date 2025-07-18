use crate::{
    plugins::canvas::client::CanvasClient,
    server::{
        tool_trait::{Tool, ToolError},
        types::{
            AddPageRequest, CreateCourseRequest, CreateModuleItemRequest, CreateModuleRequest,
            CreatePageRequest, DeleteModuleItemRequest, GetCourseRequest, GetModuleItemRequest,
            GetModuleRequest, GetPageRequest, ListPagesRequest, UpdateModuleItemRequest,
            UpdateModuleRequest, UpdatePageRequest,
        },
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
        let get_course_args: GetCourseRequest =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id".into(),
            })?;

        match self
            .canvas_client
            .get_course(&get_course_args.course_id)
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

        let create_course_args: CreateCourseRequest =
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

        let course_args: GetCourseRequest =
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

        let get_module_args: GetModuleRequest =
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

        let create_module_args: CreateModuleRequest =
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

        let update_module_args: UpdateModuleRequest =
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

        let delete_module_args: GetModuleRequest =
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

        let list_mod_items_args: GetModuleRequest =
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

        let get_item_args: GetModuleItemRequest =
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

        let create_item_args: CreateModuleItemRequest =
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

        let update_module_item_args: UpdateModuleItemRequest =
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

        let delete_module_item_args: DeleteModuleItemRequest =
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

        let list_pages_args: ListPagesRequest =
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

        let get_page: GetPageRequest =
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

        let create_page_args: CreatePageRequest =
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

        let update_page_args: UpdatePageRequest =
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

        let delete_page_args: GetPageRequest =
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

pub struct AddPageToModule {
    pub canvas_client: CanvasClient,
}

#[async_trait]
impl Tool for AddPageToModule {
    fn name(&self) -> &str {
        "add_page_to_module"
    }

    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError> {
        let parsed_args = parse_args(
            self.name(),
            args,
            "course_id: String, module_id: String, page_url: String",
        )?;

        let add_page_args: AddPageRequest =
            from_value(parsed_args).map_err(|_| ToolError::InvalidArgs {
                name: self.name().into(),
                args: "course_id: String, module_id: String, page_url: String".into(),
            })?;

        match self.canvas_client.add_page_to_module(add_page_args).await {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(
                result.to_string(),
            )])),
            Err(err) => {
                let message = format!("Error adding page to module: {:?}", err);
                Err(ToolError::InternalError {
                    error_code: ErrorCode::INTERNAL_ERROR,
                    message,
                })
            }
        }
    }
}
