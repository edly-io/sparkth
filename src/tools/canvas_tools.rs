use reqwest::Method;
use rmcp::{
    ErrorData,
    handler::server::tool::Parameters,
    model::{CallToolResult, Content, ErrorCode},
    tool, tool_router,
};
use serde_json::{Value, to_value};

use crate::server::{
    mcp_server::SparkthMCPServer,
    types::{
        AuthorizationPayload, CanvasResponse, CourseParams, CoursePayload, EnrollmentPayload,
        ListPagesPayload, ModuleItemParams, ModuleItemPayload, ModuleParams, ModulePayload,
        PageParams, PagePayload, QuestionParams, QuestionPayload, QuizParams, QuizPayload,
        UpdateModuleItemPayload, UpdateModulePayload, UpdatePagePayload, UpdateQuestionPayload,
        UpdateQuizPayload, UserPayload,
    },
};

#[tool_router(router = canvas_tools_router, vis = "pub")]
impl SparkthMCPServer {
    fn handle_response_single(&self, response: CanvasResponse) -> CallToolResult {
        let result = match response {
            CanvasResponse::Single(val) => val,
            CanvasResponse::Multiple(mut vals) => vals.pop().unwrap_or(Value::Null),
        };

        CallToolResult::success(vec![Content::text(result.to_string())])
    }

    fn handle_response_vec(&self, response: CanvasResponse) -> CallToolResult {
        let results = match response {
            CanvasResponse::Single(val) => vec![val],
            CanvasResponse::Multiple(vals) => vals,
        };

        let results: Vec<String> = results
            .into_iter()
            .map(|result| result.to_string())
            .collect();

        CallToolResult::success(vec![Content::text(results.join(","))])
    }

    #[tool(description = "Store the API URL and token from the user to authenticate requests")]
    pub async fn authenticate_user(
        &self,
        Parameters(AuthorizationPayload { api_url, api_token }): Parameters<AuthorizationPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self.canvas_client.authenticate(api_url, api_token).await {
            Ok(_) => Ok(CallToolResult::success(vec![Content::text(
                "User authorized successfuly!",
            )])),
            Err(err) => {
                let msg = format!("Error while authorization: {err}");
                Err(ErrorData::new(ErrorCode::RESOURCE_NOT_FOUND, msg, None))
            }
        }
    }

    #[tool(description = "Get all courses from Canvas account")]
    pub async fn canvas_get_courses(&self) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(Method::GET, "courses", None)
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
        description = "Get a single course from Canvas account. Always prompt for missing required parameters."
    )]
    pub async fn canvas_get_course(
        &self,
        Parameters(CourseParams { course_id }): Parameters<CourseParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(Method::GET, &format!("courses/{course_id}"), None)
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
        description = "Create a new course on Canvas. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_course(
        &self,
        Parameters(payload): Parameters<CoursePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Get all modules of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_list_modules(
        &self,
        Parameters(CourseParams { course_id }): Parameters<CourseParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(Method::GET, &format!("courses/{course_id}/modules"), None)
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
        description = "Get a single module of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_get_module(
        &self,
        Parameters(ModuleParams {
            course_id,
            module_id,
        }): Parameters<ModuleParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Create a new module for a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_module(
        &self,
        Parameters(payload): Parameters<ModulePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Update a module of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_update_module(
        &self,
        Parameters(payload): Parameters<UpdateModulePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Delete a module of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_delete_module(
        &self,
        Parameters(ModuleParams {
            course_id,
            module_id,
        }): Parameters<ModuleParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "List all modules items of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_list_module_items(
        &self,
        Parameters(ModuleParams {
            course_id,
            module_id,
        }): Parameters<ModuleParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Get a single module item of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_get_module_item(
        &self,
        Parameters(ModuleItemParams {
            course_id,
            module_id,
            item_id,
        }): Parameters<ModuleItemParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Create a new module item for a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_module_item(
        &self,
        Parameters(payload): Parameters<ModuleItemPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Update a module item of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_update_module_item(
        &self,
        Parameters(payload): Parameters<UpdateModuleItemPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Delete a module item of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_delete_module_item(
        &self,
        Parameters(ModuleItemParams {
            course_id,
            module_id,
            item_id,
        }): Parameters<ModuleItemParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "List all pages of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_list_pages(
        &self,
        Parameters(payload): Parameters<ListPagesPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Get a single page of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_get_page(
        &self,
        Parameters(PageParams {
            course_id,
            page_url,
        }): Parameters<PageParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Create a new page for a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_page(
        &self,
        Parameters(payload): Parameters<PagePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Update a page of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_update_page(
        &self,
        Parameters(payload): Parameters<UpdatePagePayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Delete a page of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_delete_page(
        &self,
        Parameters(PageParams {
            course_id,
            page_url,
        }): Parameters<PageParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "List all quizzes of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_list_quizzes(
        &self,
        Parameters(CourseParams { course_id }): Parameters<CourseParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(Method::GET, &format!("courses/{course_id}/quizzes"), None)
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
        description = "Get a single quiz of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_get_quiz(
        &self,
        Parameters(QuizParams { course_id, quiz_id }): Parameters<QuizParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Create a new quiz for a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_quiz(
        &self,
        Parameters(payload): Parameters<QuizPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Update a quiz of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_update_quiz(
        &self,
        Parameters(payload): Parameters<UpdateQuizPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Delete a quiz of a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_delete_quiz(
        &self,
        Parameters(QuizParams { course_id, quiz_id }): Parameters<QuizParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "List all questions of a quiz. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_list_questions(
        &self,
        Parameters(QuizParams { course_id, quiz_id }): Parameters<QuizParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Get a single question of a quiz. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_get_question(
        &self,
        Parameters(QuestionParams {
            course_id,
            quiz_id,
            question_id,
        }): Parameters<QuestionParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Create a new question for a quiz. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_question(
        &self,
        Parameters(payload): Parameters<QuestionPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Update a question of a quiz. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_update_question(
        &self,
        Parameters(payload): Parameters<UpdateQuestionPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Delete a question of a quiz. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_delete_question(
        &self,
        Parameters(QuestionParams {
            course_id,
            quiz_id,
            question_id,
        }): Parameters<QuestionParams>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Create a new user in a Canvas account. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_create_user(
        &self,
        Parameters(payload): Parameters<UserPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
        description = "Enroll a user in a Canvas course. Always prompt for any missing required parameters."
    )]
    pub async fn canvas_enroll_user(
        &self,
        Parameters(payload): Parameters<EnrollmentPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        match self
            .canvas_client
            .request(
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
