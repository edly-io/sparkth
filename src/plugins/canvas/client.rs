use reqwest::{Client, Method, Response};
use serde_json::{Value, from_value};
use std::collections::HashMap;

use crate::server::{
    error::CanvasError,
    types::{
        AddPageRequest, AddQuizRequest, CanvasPage, CanvasResponse, CreateCourseRequest,
        CreateModuleItemRequest, CreateModuleRequest, CreatePageRequest, CreateQuestionRequest,
        CreateQuizRequest, DeleteModuleItemRequest, GetCourseRequest, GetModuleItemRequest,
        GetModuleRequest, GetPageRequest, GetQuestionRequest, GetQuizRequest, ListPagesRequest,
        ModuleItemCompletionRequirement, Quiz, UpdateModuleItemRequest, UpdateModuleRequest,
        UpdatePageRequest, UpdateQuestionRequest, UpdateQuizRequest,
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
        method: &str,
        endpoint: &str,
        params: Option<&HashMap<String, String>>,
        data: Option<&HashMap<String, String>>,
    ) -> Result<CanvasResponse, CanvasError> {
        let url = format!("{}/{}", self.api_url, endpoint.trim_start_matches('/'));

        eprintln!(
            "Canvas API request: url={} method={} params={:?} data={:?}",
            url, method, params, data
        );

        let http_method = match method.to_uppercase().as_str() {
            "GET" => Method::GET,
            "POST" => Method::POST,
            "PUT" => Method::PUT,
            "DELETE" => Method::DELETE,
            _ => return Err(CanvasError::InvalidMethod(method.to_string())),
        };

        let mut request = self
            .client
            .request(http_method, &url)
            .header("Authorization", format!("Bearer {}", self.api_token));

        if let Some(params) = params {
            request = request.query(params);
        }

        if let Some(data) = data {
            request = request.form(data);
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

        let json_value: Value = serde_json::from_str(&response_text)?;

        match json_value {
            Value::Array(arr) => Ok(CanvasResponse::Multiple(arr)),
            single => Ok(CanvasResponse::Single(single)),
        }
    }

    async fn handle_error_response(&self, response: Response) -> Result<CanvasError, CanvasError> {
        let status_code = response.status().as_u16();
        let error_text = response.text().await?;

        let error_message = if let Ok(error_json) = serde_json::from_str::<Value>(&error_text) {
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

    pub async fn get_courses(&self) -> Result<Vec<Value>, CanvasError> {
        match self.request("GET", "courses", None, None).await? {
            CanvasResponse::Multiple(courses) => Ok(courses),
            CanvasResponse::Single(course) => Ok(vec![course]),
        }
    }

    pub async fn get_course(&self, course_id: &str) -> Result<Value, CanvasError> {
        match self
            .request("GET", &format!("courses/{}", course_id), None, None)
            .await?
        {
            CanvasResponse::Single(course) => Ok(course),
            CanvasResponse::Multiple(mut courses) => Ok(courses.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn create_course(&self, args: CreateCourseRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("course[name]".to_string(), args.name.to_string());
        data.insert("enroll_me".to_string(), "true".to_string());

        if let Some(code) = args.course_code {
            data.insert("course[course_code]".to_string(), code.to_string());
        }

        if let Some(sis_id) = args.sis_course_id {
            data.insert("course[sis_course_id]".to_string(), sis_id.to_string());
        }

        match self
            .request(
                "POST",
                &format!("accounts/{}/courses", args.account_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(course) => Ok(course),
            CanvasResponse::Multiple(mut courses) => Ok(courses.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn list_modules(&self, args: GetCourseRequest) -> Result<Vec<Value>, CanvasError> {
        match self
            .request(
                "GET",
                &format!("courses/{}/modules", args.course_id),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(modules) => Ok(modules),
            CanvasResponse::Single(module) => Ok(vec![module]),
        }
    }

    pub async fn get_module(&self, args: GetModuleRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "GET",
                &format!("courses/{}/modules/{}", args.course_id, args.module_id),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
            CanvasResponse::Single(module) => Ok(module),
        }
    }

    pub async fn create_module(&self, args: CreateModuleRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("module[name]".to_string(), args.name.to_string());

        if let Some(position) = args.position {
            data.insert("module[position]".to_string(), position.to_string());
        }

        if let Some(unlock_at) = args.unlock_at {
            data.insert("module[unlock_at]".to_string(), unlock_at.to_string());
        }

        if let Some(require_sequential_progress) = args.require_sequential_progress {
            data.insert(
                "module[require_sequential_progress]".to_string(),
                require_sequential_progress.to_string(),
            );
        }

        if let Some(prerequisite_module_ids) = args.prerequisite_module_ids {
            for (index, module_id) in prerequisite_module_ids.iter().enumerate() {
                data.insert(
                    format!("module[prerequisite_module_ids][{index}]"),
                    module_id.clone(),
                );
            }
        }

        if let Some(publish_final_grade) = args.publish_final_grade {
            data.insert(
                "module[publish_final_grade]".to_string(),
                publish_final_grade.to_string(),
            );
        }

        match self
            .request(
                "POST",
                &format!("courses/{}/modules", args.course_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn update_module(&self, args: UpdateModuleRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();

        if let Some(module_name) = args.name {
            data.insert("module[name]".to_string(), module_name.to_string());
        }

        if let Some(pos) = args.position {
            data.insert("module[position]".to_string(), pos.to_string());
        }

        if let Some(unlock) = args.unlock_at {
            data.insert("module[unlock_at]".to_string(), unlock.to_string());
        }

        if let Some(sequential) = args.require_sequential_progress {
            data.insert(
                "module[require_sequential_progress]".to_string(),
                sequential.to_string(),
            );
        }

        if let Some(prereq_ids) = args.prerequisite_module_ids {
            if prereq_ids.is_empty() {
                data.insert(
                    "module[prerequisite_module_ids][]".to_string(),
                    "".to_string(),
                );
            } else {
                for (i, prereq_id) in prereq_ids.iter().enumerate() {
                    data.insert(
                        format!("module[prerequisite_module_ids][{}]", i),
                        prereq_id.clone(),
                    );
                }
            }
        }

        if let Some(publish) = args.publish_final_grade {
            data.insert(
                "module[publish_final_grade]".to_string(),
                publish.to_string(),
            );
        }

        match self
            .request(
                "PUT",
                &format!("courses/{}/modules/{}", args.course_id, args.module_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn delete_module(&self, args: GetModuleRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "DELETE",
                &format!("courses/{}/modules/{}", args.course_id, args.module_id),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn list_module_items(
        &self,
        args: GetModuleRequest,
    ) -> Result<Vec<Value>, CanvasError> {
        match self
            .request(
                "GET",
                &format!(
                    "courses/{}/modules/{}/items",
                    args.course_id, args.module_id
                ),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(items) => Ok(items),
            CanvasResponse::Single(item) => Ok(vec![item]),
        }
    }

    pub async fn get_module_item(&self, args: GetModuleItemRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "GET",
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    args.course_id, args.module_id, args.item_id
                ),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Single(item) => Ok(item),
            CanvasResponse::Multiple(mut items) => Ok(items.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn create_module_item(
        &self,
        args: CreateModuleItemRequest,
    ) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("module_item[title]".to_string(), args.title.to_string());
        data.insert("module_item[type]".to_string(), args.item_type.to_string());

        if !args.item_type.eq("ExternalUrl") {
            if let Some(content) = args.content_id {
                data.insert("module_item[content_id]".to_string(), content.to_string());
            }
        }

        if let Some(pos) = args.position {
            data.insert("module_item[position]".to_string(), pos.to_string());
        }

        if let Some(indent_level) = args.indent {
            data.insert("module_item[indent]".to_string(), indent_level.to_string());
        }

        if let Some(url) = args.page_url {
            if args.item_type.eq("Page") {
                data.insert("module_item[page_url]".to_string(), url.to_string());
            }
        }

        if let Some(url) = args.external_url {
            if args.item_type.eq("ExternalUrl") {
                data.insert("module_item[external_url]".to_string(), url.to_string());
            }
        }

        if let Some(new_tab_val) = args.new_tab {
            data.insert("module_item[new_tab]".to_string(), new_tab_val.to_string());
        }

        if let Some(completion) = args.completion_requirement {
            data.insert(
                "module_item[completion_requirement][type]".to_string(),
                completion.requirement_type.to_string(),
            );

            if let Some(min_score) = completion.min_score {
                data.insert(
                    "module_item[completion_requirement][min_score]".to_string(),
                    min_score.to_string(),
                );
            }
        }

        match self
            .request(
                "POST",
                &format!(
                    "courses/{}/modules/{}/items",
                    args.course_id, args.module_id
                ),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(item) => Ok(item),
            CanvasResponse::Multiple(mut items) => Ok(items.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn update_module_item(
        &self,
        args: UpdateModuleItemRequest,
    ) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();

        if let Some(title) = args.title {
            data.insert("module_item[title]".to_string(), title);
        }

        if let Some(position) = args.position {
            data.insert("module_item[position]".to_string(), position.to_string());
        }

        if let Some(indent) = args.indent {
            data.insert("module_item[indent]".to_string(), indent.to_string());
        }

        if let Some(external_url) = args.external_url {
            data.insert("module_item[external_url]".to_string(), external_url);
        }

        if let Some(new_tab) = args.new_tab {
            data.insert("module_item[new_tab]".to_string(), new_tab.to_string());
        }

        if let Some(completion) = args.completion_requirement {
            data.insert(
                "module_item[completion_requirement][type]".to_string(),
                completion.requirement_type.to_string(),
            );

            if let Some(min_score) = completion.min_score {
                data.insert(
                    "module_item[completion_requirement][min_score]".to_string(),
                    min_score.to_string(),
                );
            }
        }

        match self
            .request(
                "PUT",
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    args.course_id, args.module_id, args.item_id
                ),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(item) => Ok(item),
            CanvasResponse::Multiple(mut items) => Ok(items.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn delete_module_item(
        &self,
        args: DeleteModuleItemRequest,
    ) -> Result<Value, CanvasError> {
        match self
            .request(
                "DELETE",
                &format!(
                    "courses/{}/modules/{}/items/{}",
                    args.course_id, args.module_id, args.item_id
                ),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn list_pages(&self, args: ListPagesRequest) -> Result<Vec<Value>, CanvasError> {
        let mut data = HashMap::new();

        if let Some(term) = args.search_term {
            data.insert("search_term".to_string(), term.to_string());
        }

        match self
            .request(
                "GET",
                &format!("courses/{}/pages", args.course_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Multiple(pages) => Ok(pages),
            CanvasResponse::Single(page) => Ok(vec![page]),
        }
    }

    pub async fn get_page(&self, args: GetPageRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "GET",
                &format!("courses/{}/pages/{}", args.course_id, args.page_url),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
            CanvasResponse::Single(module) => Ok(module),
        }
    }

    pub async fn create_page(&self, args: CreatePageRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("wiki_page[title]".to_string(), args.title);
        data.insert("wiki_page[body]".to_string(), args.body);

        if let Some(editing_roles) = args.editing_roles {
            data.insert("wiki_page[editing_roles]".to_string(), editing_roles);
        }

        if let Some(published) = args.published {
            data.insert("wiki_page[published]".to_string(), published.to_string());
        }

        if let Some(front_page) = args.front_page {
            data.insert("wiki_page[front_page]".to_string(), front_page.to_string());
        }

        match self
            .request(
                "POST",
                &format!("courses/{}/pages", args.course_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn update_page(&self, args: UpdatePageRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();

        if let Some(new_title) = args.title {
            data.insert("wiki_page[title]".to_string(), new_title);
        }

        if let Some(new_body) = args.body {
            data.insert("wiki_page[body]".to_string(), new_body);
        }

        if let Some(roles) = args.editing_roles {
            data.insert("wiki_page[editing_roles]".to_string(), roles);
        }

        if let Some(is_published) = args.published {
            data.insert("wiki_page[published]".to_string(), is_published.to_string());
        }

        if let Some(is_front_page) = args.front_page {
            data.insert(
                "wiki_page[front_page]".to_string(),
                is_front_page.to_string(),
            );
        }

        match self
            .request(
                "PUT",
                &format!("courses/{}/pages/{}", args.course_id, args.page_url),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn delete_page(&self, args: GetPageRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "DELETE",
                &format!("courses/{}/pages/{}", args.course_id, args.page_url),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn add_page_to_module(&self, args: AddPageRequest) -> Result<Value, CanvasError> {
        let page = self
            .get_page(GetPageRequest {
                course_id: args.course_id.clone(),
                page_url: args.page_url.clone(),
            })
            .await?;
        let canvas_page: CanvasPage = from_value(page)?;

        let title = args
            .title
            .or_else(|| canvas_page.title.clone())
            .unwrap_or_else(|| "Untitled Page".to_string());

        let content_id = canvas_page.page_id.map(|id| id.to_string());

        let module_item = CreateModuleItemRequest {
            module_id: args.module_id,
            course_id: args.course_id,
            title,
            item_type: "Page".to_string(),
            content_id,
            position: args.position,
            indent: args.indent,
            page_url: Some(args.page_url),
            new_tab: args.new_tab,
            external_url: None,
            completion_requirement: None,
        };

        self.create_module_item(module_item).await
    }

    pub async fn list_quizzes(&self, args: GetCourseRequest) -> Result<Vec<Value>, CanvasError> {
        match self
            .request(
                "GET",
                &format!("courses/{}/quizzes", args.course_id),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(pages) => Ok(pages),
            CanvasResponse::Single(page) => Ok(vec![page]),
        }
    }

    pub async fn get_quiz(&self, args: GetQuizRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "GET",
                &format!("courses/{}/quizzes/{}", args.course_id, args.quiz_id),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
            CanvasResponse::Single(module) => Ok(module),
        }
    }

    pub async fn create_quiz(&self, args: CreateQuizRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("quiz[title]".to_string(), args.title);
        data.insert("quiz[description]".to_string(), args.description);
        data.insert("quiz[quiz_type]".to_string(), args.quiz_type);

        if let Some(published) = args.published {
            data.insert("quiz[published]".to_string(), published.to_string());
        }

        if let Some(time_limit) = args.time_limit {
            data.insert("quiz[time_limit]".to_string(), time_limit.to_string());
        }

        match self
            .request(
                "POST",
                &format!("courses/{}/quizzes", args.course_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(quiz) => Ok(quiz),
            CanvasResponse::Multiple(mut quizzes) => Ok(quizzes.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn update_quiz(&self, args: UpdateQuizRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert(
            "quiz[notify_of_update]".to_string(),
            args.notify_of_update.to_string(),
        );

        if let Some(new_title) = args.title {
            data.insert("quiz[title]".to_string(), new_title);
        }

        if let Some(new_description) = args.description {
            data.insert("quiz[description]".to_string(), new_description);
        }

        if let Some(quiz_type) = args.quiz_type {
            data.insert("quiz[quiz_type]".to_string(), quiz_type);
        }

        if let Some(published) = args.published {
            data.insert("quiz[published]".to_string(), published.to_string());
        }

        if let Some(time_limit) = args.time_limit {
            data.insert("quiz[time_limit]".to_string(), time_limit.to_string());
        }

        match self
            .request(
                "PUT",
                &format!("courses/{}/quizzes/{}", args.course_id, args.quiz_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn delete_quiz(&self, args: GetQuizRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "DELETE",
                &format!("courses/{}/quizzes/{}", args.course_id, args.quiz_id),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn add_quiz_to_module(&self, args: AddQuizRequest) -> Result<Value, CanvasError> {
        let quiz = self
            .get_quiz(GetQuizRequest {
                course_id: args.course_id.clone(),
                quiz_id: args.quiz_id.clone(),
            })
            .await?;

        let quiz: Quiz = from_value(quiz)?;

        let title = args
            .title
            .or_else(|| quiz.title.clone())
            .unwrap_or_else(|| "Untitled Quiz".to_string());

        let content_id = quiz.quiz_id.map(|id| id.to_string());

        let quiz_module_item = CreateModuleItemRequest {
            module_id: args.module_id,
            course_id: args.course_id,
            title,
            item_type: "Quiz".to_string(),
            content_id,
            position: args.position,
            indent: args.indent,
            page_url: None,
            new_tab: args.new_tab,
            external_url: None,
            completion_requirement: Some(ModuleItemCompletionRequirement {
                requirement_type: "must_submit".to_string(),
                min_score: None,
            }),
        };

        self.create_module_item(quiz_module_item).await
    }

    pub async fn list_questions(&self, args: GetQuizRequest) -> Result<Vec<Value>, CanvasError> {
        match self
            .request(
                "GET",
                &format!(
                    "courses/{}/quizzes/{}/questions",
                    args.course_id, args.quiz_id
                ),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(pages) => Ok(pages),
            CanvasResponse::Single(page) => Ok(vec![page]),
        }
    }

    pub async fn get_question(&self, args: GetQuestionRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "GET",
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    args.course_id, args.quiz_id, args.question_id
                ),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
            CanvasResponse::Single(module) => Ok(module),
        }
    }

    pub async fn create_question(&self, args: CreateQuestionRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("question[question_name]".to_string(), args.name);
        data.insert("question[question_text]".to_string(), args.text);
        data.insert(
            "question[question_type]".to_string(),
            "multiple_choice_question".to_string(),
        );

        for (i, answer) in args.answers.iter().enumerate() {
            data.insert(
                format!("question[answers][{i}][answer_text]"),
                answer.answer_text.clone(),
            );
            data.insert(
                format!("question[answers][{i}][answerweight]"),
                answer.answer_weight.to_string(),
            );

            if let Some(comments) = &answer.answer_comments {
                data.insert(
                    format!("question[answers][{i}][answer_comments]"),
                    comments.clone(),
                );
            }
        }

        if let Some(points_possible) = args.points_possible {
            data.insert(
                "question[points_possible]".to_string(),
                points_possible.to_string(),
            );
        }

        match self
            .request(
                "POST",
                &format!(
                    "courses/{}/quizzes/{}/questions",
                    args.course_id, args.quiz_id
                ),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(quiz) => Ok(quiz),
            CanvasResponse::Multiple(mut quizzes) => Ok(quizzes.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn update_question(&self, args: UpdateQuestionRequest) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();

        if let Some(name) = args.name {
            data.insert("question[question_name]".to_string(), name);
        }

        if let Some(text) = args.text {
            data.insert("question[question_text]".to_string(), text);
        }

        if let Some(question_type) = args.question_type {
            data.insert("question[question_type]".to_string(), question_type);
        }

        if let Some(points_possible) = args.points_possible {
            data.insert(
                "question[points_possible]".to_string(),
                points_possible.to_string(),
            );
        }

        if let Some(answers) = args.answers {
            for (i, answer) in answers.iter().enumerate() {
                data.insert(
                    format!("question[answers][{i}][answer_text]"),
                    answer.answer_text.clone(),
                );
                data.insert(
                    format!("question[answers][{i}][answerweight]"),
                    answer.answer_weight.to_string(),
                );

                if let Some(comments) = &answer.answer_comments {
                    data.insert(
                        format!("question[answers][{i}][answer_comments]"),
                        comments.clone(),
                    );
                }
            }
        }

        match self
            .request(
                "PUT",
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    args.course_id, args.quiz_id, args.question_id
                ),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }

    pub async fn delete_question(&self, args: GetQuestionRequest) -> Result<Value, CanvasError> {
        match self
            .request(
                "DELETE",
                &format!(
                    "courses/{}/quizzes/{}/questions/{}",
                    args.course_id, args.quiz_id, args.question_id
                ),
                None,
                None,
            )
            .await?
        {
            CanvasResponse::Single(module) => Ok(module),
            CanvasResponse::Multiple(mut modules) => Ok(modules.pop().unwrap_or(Value::Null)),
        }
    }
}
