use reqwest::{Client, Method, Response};
use serde_json::{from_str, to_value, Value};

use crate::server::{
    error::CanvasError,
    types::{
        CanvasResponse, CourseParams, CoursePayload, EnrollmentPayload,
        ListPagesPayload, ListUsersParams, ModuleItemParams, ModuleItemPayload, ModuleParams,
        ModulePayload, PageParams, PagePayload, QuestionParams, QuestionPayload, QuizParams,
        QuizPayload, UpdateModuleItemPayload, UpdateModulePayload, UpdatePagePayload,
        UpdateQuestionPayload, UpdateQuizPayload, UserPayload,
    },
};

#[derive(Debug, Clone)]
pub struct CanvasClient {
    api_url: String,
    api_token: String,
    client: Client,
}

impl CanvasClient {
    pub fn new(api_url: String, api_token: String) -> Self {
        let client = Client::new();
        Self {
            api_url: api_url.trim_end_matches('/').to_string(),
            api_token,
            client,
        }
    }

    async fn request(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<CanvasResponse, CanvasError> {
        let url = format!("{}/{}", self.api_url, endpoint.trim_start_matches('/'));

        let mut request = self
            .client
            .request(http_method, &url)
            .header("Authorization", format!("Bearer {}", self.api_token));

        if let Some(payload) = payload {
            request = request.json(&payload);
        }

        let response = request.send().await?;

        if !response.status().is_success() {
            return Err(self.handle_error_response(response).await?);
        }

        let response_text = response.text().await?;

        if response_text.is_empty() {
            return Ok(CanvasResponse::Single(
                Value::Object(serde_json::Map::new()),
            ));
        }

        let json_value: Value = from_str(&response_text)?;

        match json_value {
            Value::Array(arr) => Ok(CanvasResponse::Multiple(arr)),
            single => Ok(CanvasResponse::Single(single)),
        }
    }

    async fn handle_error_response(&self, response: Response) -> Result<CanvasError, CanvasError> {
        let status_code = response.status().as_u16();
        let error_text = response.text().await?;

        let error_message = if let Ok(error_json) = from_str::<Value>(&error_text) {
            if let Some(errors) = error_json.get("errors") {
                match errors {
                    Value::Object(obj) => obj
                        .get("message")
                        .and_then(|v| v.as_str())
                        .unwrap_or(&error_text)
                        .to_string(),
                    Value::Array(arr) => {
                        if let Some(first_error) = arr.first() {
                            first_error.as_str().unwrap_or(&error_text).to_string()
                        } else {
                            error_text
                        }
                    }
                    _ => error_text,
                }
            } else if let Some(message) = error_json.get("message") {
                message.as_str().unwrap_or(&error_text).to_string()
            } else {
                error_text
            }
        } else {
            error_text
        };

        Ok(CanvasError::ApiError {
            status_code,
            message: error_message,
        })
    }

    fn unwrap_canvas_response_single(
        &self,
        response: CanvasResponse,
    ) -> Result<Value, CanvasError> {
        match response {
            CanvasResponse::Single(val) => Ok(val),
            CanvasResponse::Multiple(mut vals) => Ok(vals.pop().unwrap_or(Value::Null)),
        }
    }

    fn unwrap_canvas_response_vec(
        &self,
        response: CanvasResponse,
    ) -> Result<Vec<Value>, CanvasError> {
        match response {
            CanvasResponse::Single(val) => Ok(vec![val]),
            CanvasResponse::Multiple(vals) => Ok(vals),
        }
    }

    pub async fn get_courses(&self) -> Result<Vec<Value>, CanvasError> {
        let response = self.request(Method::GET, "courses", None).await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn get_course(&self, course_id: u32) -> Result<Value, CanvasError> {
        let response = self
            .request(Method::GET, &format!("courses/{}", course_id), None)
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn create_course(&self, args: CoursePayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!("accounts/{}/courses", args.account_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn list_modules(&self, args: CourseParams) -> Result<Vec<Value>, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("courses/{}/modules", args.course_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn get_module(&self, args: ModuleParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("courses/{}/modules/{}", args.course_id, args.module_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn create_module(&self, args: ModulePayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!("courses/{}/modules", args.course_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn update_module(&self, args: UpdateModulePayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::PUT,
                &format!("courses/{}/modules/{}", args.course_id, args.module_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn delete_module(&self, args: ModuleParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::DELETE,
                &format!("courses/{}/modules/{}", args.course_id, args.module_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn list_module_items(&self, args: ModuleParams) -> Result<Vec<Value>, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!(
                    "courses/{}/modules/{}/items",
                    args.course_id, args.module_id
                ),
                None,
            )
            .await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn get_module_item(&self, args: ModuleItemParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    args.course_id, args.module_id, args.item_id
                ),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn create_module_item(&self, args: ModuleItemPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!(
                    "courses/{}/modules/{}/items",
                    args.course_id, args.module_id
                ),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn update_module_item(
        &self,
        args: UpdateModuleItemPayload,
    ) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::PUT,
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    args.course_id, args.module_id, args.item_id
                ),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn delete_module_item(
        &self,
        args: ModuleItemParams,
    ) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::DELETE,
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    args.course_id, args.module_id, args.item_id
                ),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn list_pages(&self, args: ListPagesPayload) -> Result<Vec<Value>, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("courses/{}/pages", args.course_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn get_page(&self, args: PageParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("courses/{}/pages/{}", args.course_id, args.page_url),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn create_page(&self, args: PagePayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!("courses/{}/pages", args.course_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn update_page(&self, args: UpdatePagePayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::PUT,
                &format!("courses/{}/pages/{}", args.course_id, args.url_or_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn delete_page(&self, args: PageParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::DELETE,
                &format!("courses/{}/pages/{}", args.course_id, args.page_url),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    // pub async fn add_page_to_module(&self, args: AddPageParams) -> Result<Value, CanvasError> {
    //     let page = self
    //         .get_page(PageParams {
    //             course_id: args.course_id.clone(),
    //             page_url: args.page_url.clone(),
    //         })
    //         .await?;
    //     let canvas_page: CanvasPage = from_value(page)?;

    //     let title = args
    //         .title
    //         .or_else(|| canvas_page.title.clone())
    //         .unwrap_or_else(|| "Untitled Page".to_string());

    //     let content_id = canvas_page.page_id.map(|id| id.to_string());

    //     let module_item = ModuleItemPayload {
    //         module_id: args.module_id,
    //         course_id: args.course_id,
    //         module_item: ModuleItem {
    //             title,
    //             item_type: ModuleItemType::Pa,
    //             content_id,
    //             position: args.position,
    //             indent: args.indent,
    //             page_url: Some(args.page_url),
    //             new_tab: args.new_tab,
    //             external_url: None,
    //             completion_requirement: None,
    //         }
    //     };

    //     self.create_module_item(module_item).await
    // }

    pub async fn list_quizzes(&self, args: CourseParams) -> Result<Vec<Value>, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("courses/{}/quizzes", args.course_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn get_quiz(&self, args: QuizParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("courses/{}/quizzes/{}", args.course_id, args.quiz_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn create_quiz(&self, args: QuizPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!("courses/{}/quizzes", args.course_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn update_quiz(&self, args: UpdateQuizPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::PUT,
                &format!("courses/{}/quizzes/{}", args.course_id, args.quiz_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn delete_quiz(&self, args: QuizParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::DELETE,
                &format!("courses/{}/quizzes/{}", args.course_id, args.quiz_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    // pub async fn add_quiz_to_module(&self, args: AddQuizRequest) -> Result<Value, CanvasError> {
    //     let quiz = self
    //         .get_quiz(QuizParams {
    //             course_id: args.course_id.clone(),
    //             quiz_id: args.quiz_id.clone(),
    //         })
    //         .await?;

    //     let quiz_module_item = CreateModuleItemRequest {
    //         module_id: args.module_id,
    //         course_id: args.course_id,
    //         title,
    //         item_type: "Quiz".to_string(),
    //         content_id,
    //         position: args.position,
    //         indent: args.indent,
    //         page_url: None,
    //         new_tab: args.new_tab,
    //         external_url: None,
    //         completion_requirement: Some(ModuleItemCompletionRequirement {
    //             requirement_type: "must_submit".to_string(),
    //             min_score: None,
    //         }),
    //     };

    //     self.create_module_item(quiz_module_item).await
    // }

    pub async fn list_questions(&self, args: QuizParams) -> Result<Vec<Value>, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!(
                    "courses/{}/quizzes/{}/questions",
                    args.course_id, args.quiz_id
                ),
                None,
            )
            .await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn get_question(&self, args: QuestionParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    args.course_id, args.quiz_id, args.question_id
                ),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn create_question(&self, args: QuestionPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!(
                    "courses/{}/quizzes/{}/questions",
                    args.course_id, args.quiz_id
                ),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn update_question(&self, args: UpdateQuestionPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::PUT,
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    args.course_id, args.quiz_id, args.question_id
                ),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn delete_question(&self, args: QuestionParams) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::DELETE,
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    args.course_id, args.quiz_id, args.question_id
                ),
                None,
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn list_users(&self, args: ListUsersParams) -> Result<Vec<Value>, CanvasError> {
        let response = self
            .request(
                Method::GET,
                &format!("accounts/{}/users", args.account_id),
                None,
            )
            .await?;
        self.unwrap_canvas_response_vec(response)
    }

    pub async fn create_user(&self, args: UserPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!("accounts/{}/users", args.account_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }

    pub async fn enroll_user(&self, args: EnrollmentPayload) -> Result<Value, CanvasError> {
        let response = self
            .request(
                Method::POST,
                &format!("courses/{}/enrollments", args.course_id),
                Some(to_value(args).unwrap()),
            )
            .await?;
        self.unwrap_canvas_response_single(response)
    }
}
