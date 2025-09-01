use crate::utils::cached_schema_for_type;
use crate::{
    plugins::{
        canvas::{
            client::CanvasClient,
            types::{
                AuthenticationPayload, CourseParams, CoursePayload, EnrollmentPayload,
                ListPagesPayload, ModuleItemParams, ModuleItemPayload, ModuleParams, ModulePayload,
                PageParams, PagePayload, QuestionParams, QuestionPayload, QuizParams, QuizPayload,
                UpdateModuleItemPayload, UpdateModulePayload, UpdatePagePayload,
                UpdateQuestionPayload, UpdateQuizPayload, UserPayload,
            },
        },
        response::LMSResponse,
    },
    server::mcp_server::SparkthMCPServer,
};
use reqwest::Method;
use rmcp::{
    ErrorData,
    handler::server::tool::Parameters,
    model::{CallToolResult, Content, ErrorCode},
    tool, tool_router,
};
use serde_json::{Value, to_value};

#[tool_router(router = canvas_tools_router, vis = "pub")]
impl SparkthMCPServer {
    pub fn handle_response_single(&self, response: LMSResponse) -> CallToolResult {
        let result = match response {
            LMSResponse::Single(val) => val,
            LMSResponse::Multiple(mut vals) => vals.pop().unwrap_or(Value::Null),
        };

        CallToolResult::success(vec![Content::text(result.to_string())])
    }

    pub fn handle_response_vec(&self, response: LMSResponse) -> CallToolResult {
        let results = match response {
            LMSResponse::Single(val) => vec![val],
            LMSResponse::Multiple(vals) => vals,
        };

        let results: Vec<String> = results
            .into_iter()
            .map(|result| result.to_string())
            .collect();

        CallToolResult::success(vec![Content::text(results.join(","))])
    }

    #[tool(
        description = "Store the API URL and token from the user to authenticate requests",
        input_schema = cached_schema_for_type::<AuthenticationPayload>())
    ]
    pub async fn canvas_authenticate(
        &self,
        Parameters(AuthenticationPayload { api_url, api_token }): Parameters<AuthenticationPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match CanvasClient::authenticate(api_url, api_token).await {
            Ok(_) => Ok(CallToolResult::success(vec![Content::text(
                "User authenticated successfuly!",
            )])),
            Err(err) => {
                let msg = format!("Error while authentication: {err}");
                Err(ErrorData::new(ErrorCode::RESOURCE_NOT_FOUND, msg, None))
            }
        }
    }

    #[tool(
        description = "Get all courses from Canvas account. Don't proceed until credentials are authenticated.",
        input_schema = cached_schema_for_type::<AuthenticationPayload>()
    )]
    pub async fn canvas_get_courses(
        &self,
        Parameters(AuthenticationPayload { api_url, api_token }): Parameters<AuthenticationPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(api_url, api_token);

        match client.request_bearer(Method::GET, "courses", None).await {
            Ok(response) => Ok(self.handle_response_vec(response)),
            Err(err) => {
                let msg = format!("Error while fetching all courses: {err}");
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get a single course from Canvas account. Don't proceed until credentials are authenticated.",
        input_schema = cached_schema_for_type::<CourseParams>()
    )]
    pub async fn canvas_get_course(
        &self,
        Parameters(CourseParams { course_id, auth }): Parameters<CourseParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);
        match client
            .request_bearer(Method::GET, &format!("courses/{course_id}"), None)
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!("Error while fetching course {course_id}: {err}");
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new course on Canvas. Don't proceed until credentials are authenticated. Don't proceed until credentials are authenticated. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<CoursePayload>()
    )]
    pub async fn canvas_create_course(
        &self,
        Parameters(payload): Parameters<CoursePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!("accounts/{}/courses", payload.account_id),
                Some(to_value(payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!("Error while creating the course: {err}");
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get all modules of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<CourseParams>()
    )]
    pub async fn canvas_list_modules(
        &self,
        Parameters(CourseParams { course_id, auth }): Parameters<CourseParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(Method::GET, &format!("courses/{course_id}/modules"), None)
            .await
        {
            Ok(response) => Ok(self.handle_response_vec(response)),
            Err(err) => {
                let msg = format!("Error while fetching all courses: {err}");
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get a single module of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModuleParams>()
    )]
    pub async fn canvas_get_module(
        &self,
        Parameters(ModuleParams {
            course_id,
            module_id,
            auth,
        }): Parameters<ModuleParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/modules/{module_id}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while getting module {module_id} for course {course_id}: {err}",
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new module for a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModulePayload>()
    )]
    pub async fn canvas_create_module(
        &self,
        Parameters(payload): Parameters<ModulePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!("courses/{}/modules", payload.course_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while creating a new module for course {}: {err}",
                    payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Update a module of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<UpdateModulePayload>()
    )]
    pub async fn canvas_update_module(
        &self,
        Parameters(payload): Parameters<UpdateModulePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::PUT,
                &format!(
                    "courses/{}/modules/{}",
                    payload.course_id, payload.module_id
                ),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while updating module {} for course {}: {err}",
                    payload.module_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Delete a module of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModuleParams>()
    )]
    pub async fn canvas_delete_module(
        &self,
        Parameters(ModuleParams {
            course_id,
            module_id,
            auth,
        }): Parameters<ModuleParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::DELETE,
                &format!("courses/{course_id}/modules/{module_id}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while deleting module {module_id} for course {course_id}: {err}",
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "List all modules items of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModuleParams>()
    )]
    pub async fn canvas_list_module_items(
        &self,
        Parameters(ModuleParams {
            course_id,
            module_id,
            auth,
        }): Parameters<ModuleParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/modules/{module_id}/items"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_vec(response)),
            Err(err) => {
                let msg = format!(
                    "Error while listing module items for module {module_id} of course {course_id}: {err}",
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get a single module item of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModuleItemParams>()
    )]
    pub async fn canvas_get_module_item(
        &self,
        Parameters(ModuleItemParams {
            course_id,
            module_id,
            item_id,
            auth,
        }): Parameters<ModuleItemParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/modules/{module_id}/items/{item_id}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while fetching module item {item_id} for module {module_id} of course {course_id}: {err}",
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new module item for a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModuleItemPayload>()
    )]
    pub async fn canvas_create_module_item(
        &self,
        Parameters(payload): Parameters<ModuleItemPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!(
                    "courses/{}/modules/{}/items",
                    payload.course_id, payload.module_id
                ),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while creating new module item for module {} of course {}: {err}",
                    payload.module_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Update a module item of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<UpdateModuleItemPayload>()
    )]
    pub async fn canvas_update_module_item(
        &self,
        Parameters(payload): Parameters<UpdateModuleItemPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::PUT,
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    payload.course_id, payload.module_id, payload.item_id
                ),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while updating module item {} for module {} of course {}: {err}",
                    payload.item_id, payload.module_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Delete a module item of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ModuleItemParams>()
    )]
    pub async fn canvas_delete_module_item(
        &self,
        Parameters(ModuleItemParams {
            course_id,
            module_id,
            item_id,
            auth,
        }): Parameters<ModuleItemParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::DELETE,
                &format!("courses/{course_id}/modules/{module_id}/items/{item_id}",),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error in deleting module item {item_id} for module {module_id} of course {course_id}: {err}",
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "List all pages of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<ListPagesPayload>()
    )]
    pub async fn canvas_list_pages(
        &self,
        Parameters(payload): Parameters<ListPagesPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{}/pages", payload.course_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_vec(response)),
            Err(err) => {
                let msg = format!(
                    "Error while listing pages for course {}: {err}",
                    payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get a single page of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<PageParams>()
    )]
    pub async fn canvas_get_page(
        &self,
        Parameters(PageParams {
            course_id,
            page_url,
            auth,
        }): Parameters<PageParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/pages/{page_url}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg =
                    format!("Error while fetching page {page_url} for course {course_id}: {err}");
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new page for a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<PagePayload>()
    )]
    pub async fn canvas_create_page(
        &self,
        Parameters(payload): Parameters<PagePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!("courses/{}/pages", payload.course_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while creating a new page for course {}: {err}",
                    payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Update a page of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<UpdatePagePayload>()
    )]
    pub async fn canvas_update_page(
        &self,
        Parameters(payload): Parameters<UpdatePagePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::PUT,
                &format!("courses/{}/pages/{}", payload.course_id, payload.url_or_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while updating page {} for course {}: {err}",
                    payload.url_or_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Delete a page of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<PageParams>()
    )]
    pub async fn canvas_delete_page(
        &self,
        Parameters(PageParams {
            course_id,
            page_url,
            auth,
        }): Parameters<PageParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::DELETE,
                &format!("courses/{course_id}/pages/{page_url}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg =
                    format!("Error while deleting page {page_url} of course {course_id}: {err}",);
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "List all quizzes of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<CourseParams>()
    )]
    pub async fn canvas_list_quizzes(
        &self,
        Parameters(CourseParams { course_id, auth }): Parameters<CourseParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(Method::GET, &format!("courses/{course_id}/quizzes"), None)
            .await
        {
            Ok(response) => Ok(self.handle_response_vec(response)),
            Err(err) => {
                let msg = format!("Error while listing quizzes for course {course_id}: {err}",);
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get a single quiz of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuizParams>()
    )]
    pub async fn canvas_get_quiz(
        &self,
        Parameters(QuizParams {
            course_id,
            quiz_id,
            auth,
        }): Parameters<QuizParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/quizzes/{quiz_id}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg =
                    format!("Error while fetching quiz {quiz_id} of course {course_id}: {err}",);
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new quiz for a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuizPayload>()
    )]
    pub async fn canvas_create_quiz(
        &self,
        Parameters(payload): Parameters<QuizPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!("courses/{}/quizzes", payload.course_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while creating a new quiz for course {}: {err}",
                    payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Update a quiz of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<UpdateQuizPayload>()
    )]
    pub async fn canvas_update_quiz(
        &self,
        Parameters(payload): Parameters<UpdateQuizPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::PUT,
                &format!("courses/{}/quizzes/{}", payload.course_id, payload.quiz_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while updating quiz {} for course {}: {err}",
                    payload.quiz_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Delete a quiz of a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuizParams>()
    )]
    pub async fn canvas_delete_quiz(
        &self,
        Parameters(QuizParams {
            course_id,
            quiz_id,
            auth,
        }): Parameters<QuizParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::DELETE,
                &format!("courses/{course_id}/quizzes/{quiz_id}"),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg =
                    format!("Error while deleting quiz {quiz_id} of course {course_id}: {err}");
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "List all questions of a quiz. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuizParams>()
    )]
    pub async fn canvas_list_questions(
        &self,
        Parameters(QuizParams {
            course_id,
            quiz_id,
            auth,
        }): Parameters<QuizParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/quizzes/{quiz_id}/questions",),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_vec(response)),
            Err(err) => {
                let msg = format!(
                    "Error while listing questions for quiz {quiz_id} of course {course_id}: {err}"
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Get a single question of a quiz. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuestionParams>()
    )]
    pub async fn canvas_get_question(
        &self,
        Parameters(QuestionParams {
            course_id,
            quiz_id,
            question_id,
            auth,
        }): Parameters<QuestionParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::GET,
                &format!("courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}",),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while listing question {question_id} for quiz {quiz_id} of course {course_id}: {err}"
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new question for a quiz. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuestionPayload>()
    )]
    pub async fn canvas_create_question(
        &self,
        Parameters(payload): Parameters<QuestionPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!(
                    "courses/{}/quizzes/{}/questions",
                    payload.course_id, payload.quiz_id
                ),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while creating a new question for quiz {} of course {}: {err}",
                    payload.quiz_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Update a question of a quiz. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<UpdateQuestionPayload>()
    )]
    pub async fn canvas_update_question(
        &self,
        Parameters(payload): Parameters<UpdateQuestionPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::PUT,
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    payload.course_id, payload.quiz_id, payload.question_id
                ),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while updating question {} for quiz {} of course {}: {err}",
                    payload.question_id, payload.quiz_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Delete a question of a quiz. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<QuestionParams>()
    )]
    pub async fn canvas_delete_question(
        &self,
        Parameters(QuestionParams {
            course_id,
            quiz_id,
            question_id,
            auth,
        }): Parameters<QuestionParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = CanvasClient::new(auth.api_url, auth.api_token);

        match client
            .request_bearer(
                Method::DELETE,
                &format!("courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}",),
                None,
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while deleting question {question_id} for quiz {quiz_id} of course {course_id}: {err}"
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Create a new user in a Canvas account. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<UserPayload>()
    )]
    pub async fn canvas_create_user(
        &self,
        Parameters(payload): Parameters<UserPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!("accounts/{}/users", payload.account_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while creating new user with id {} for account {}: {err}",
                    payload.pseudonym.unique_id, payload.account_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }

    #[tool(
        description = "Enroll a user in a Canvas course. Don't proceed until credentials are authenticated. Always prompt for any missing required parameters.",
        input_schema = cached_schema_for_type::<EnrollmentPayload>()
    )]
    pub async fn canvas_enroll_user(
        &self,
        Parameters(payload): Parameters<EnrollmentPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client =
            CanvasClient::new(payload.auth.api_url.clone(), payload.auth.api_token.clone());

        match client
            .request_bearer(
                Method::POST,
                &format!("courses/{}/enrollments", payload.course_id),
                Some(to_value(&payload).unwrap()),
            )
            .await
        {
            Ok(response) => Ok(self.handle_response_single(response)),
            Err(err) => {
                let msg = format!(
                    "Error while enrolling user {} to course {}: {err}",
                    payload.enrollment.user_id, payload.course_id
                );
                Err(ErrorData::new(ErrorCode::INTERNAL_ERROR, msg, None))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::server::mcp_server::SparkthMCPServer;

    #[test]
    fn test_canvas_tool_router() {
        let canvas_tools = SparkthMCPServer::canvas_tools_router().list_all();

        assert_eq!(canvas_tools.len(), 31);
    }
}
