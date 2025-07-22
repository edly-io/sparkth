use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum CanvasResponse {
    Single(Value),
    Multiple(Vec<Value>),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Enrollment {
    pub enrollment_state: String,
    pub limit_privileges_to_course_section: bool,
    pub role: String,
    pub role_id: u64,
    #[serde(rename = "type")]
    pub enrollment_type: String,
    pub user_id: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Course {
    pub id: Option<u64>,
    pub name: String,
    pub course_code: Option<String>,
    pub sis_course_id: Option<String>,
    pub account_id: Option<u64>,
    pub workflow_state: Option<String>,
    pub enrollments: Vec<Enrollment>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
}

#[derive(Deserialize)]
pub struct GetCourseRequest {
    pub course_id: String,
}

#[derive(Deserialize)]
pub struct CreateCourseRequest {
    pub account_id: String,
    pub name: String,
    pub course_code: Option<String>,
    pub sis_course_id: Option<String>,
}

#[derive(Deserialize)]
pub struct GetModuleRequest {
    pub course_id: String,
    pub module_id: String,
}

#[derive(Deserialize)]
pub struct CreateModuleRequest {
    pub course_id: String,
    pub name: String,
    pub position: Option<u8>,
    pub unlock_at: Option<String>,
    pub require_sequential_progress: Option<bool>,
    pub prerequisite_module_ids: Option<Vec<String>>,
    pub publish_final_grade: Option<bool>,
}

#[derive(Deserialize)]
pub struct UpdateModuleRequest {
    pub course_id: String,
    pub module_id: String,
    pub name: Option<String>,
    pub position: Option<u32>,
    pub unlock_at: Option<String>,
    pub require_sequential_progress: Option<bool>,
    pub prerequisite_module_ids: Option<Vec<String>>,
    pub publish_final_grade: Option<bool>,
}

#[derive(Deserialize)]
pub struct GetModuleItemRequest {
    pub course_id: String,
    pub module_id: String,
    pub item_id: String,
}

#[derive(Deserialize)]
pub struct ModuleItemCompletionRequirement {
    pub requirement_type: String,
    pub min_score: Option<f64>,
}

#[derive(Deserialize)]
pub struct CreateModuleItemRequest {
    pub module_id: String,
    pub course_id: String,
    pub title: String,
    pub item_type: String,
    pub content_id: Option<String>,
    pub position: Option<u32>,
    pub indent: Option<u32>,
    pub page_url: Option<String>,
    pub external_url: Option<String>,
    pub new_tab: Option<bool>,
    pub completion_requirement: Option<ModuleItemCompletionRequirement>,
}

#[derive(Deserialize)]
pub struct UpdateModuleItemRequest {
    pub module_id: String,
    pub course_id: String,
    pub item_id: String,
    pub title: Option<String>,
    pub position: Option<u32>,
    pub indent: Option<u32>,
    pub external_url: Option<String>,
    pub new_tab: Option<bool>,
    pub completion_requirement: Option<ModuleItemCompletionRequirement>,
}

#[derive(Deserialize)]
pub struct DeleteModuleItemRequest {
    pub module_id: String,
    pub course_id: String,
    pub item_id: String,
}

#[derive(Deserialize)]
pub struct ListPagesRequest {
    pub course_id: String,
    pub search_term: Option<String>,
}

#[derive(Deserialize)]
pub struct GetPageRequest {
    pub course_id: String,
    pub page_url: String,
}

#[derive(Deserialize)]
pub struct CreatePageRequest {
    pub course_id: String,
    pub title: String,
    pub body: String,
    pub editing_roles: Option<String>,
    pub published: Option<bool>,
    pub front_page: Option<bool>,
}

#[derive(Deserialize)]
pub struct UpdatePageRequest {
    pub course_id: String,
    pub page_url: String,
    pub title: Option<String>,
    pub body: Option<String>,
    pub editing_roles: Option<String>,
    pub published: Option<bool>,
    pub front_page: Option<bool>,
}

#[derive(Deserialize)]
pub struct AddPageRequest {
    pub course_id: String,
    pub module_id: String,
    pub page_url: String,
    pub title: Option<String>,
    pub position: Option<u32>,
    pub indent: Option<u32>,
    pub new_tab: Option<bool>,
}

#[derive(Deserialize)]
pub struct CanvasPage {
    pub page_id: Option<u64>,
    pub title: Option<String>,
}

#[derive(Deserialize)]
pub struct GetQuizRequest {
    pub course_id: String,
    pub quiz_id: String,
}

#[derive(Deserialize)]
pub struct CreateQuizRequest {
    pub course_id: String,
    pub title: String,
    pub description: String,
    pub quiz_type: String,
    pub time_limit: Option<i32>,
    pub published: Option<bool>,
}

#[derive(Deserialize)]
pub struct UpdateQuizRequest {
    pub course_id: String,
    pub quiz_id: String,
    pub title: Option<String>,
    pub description: Option<String>,
    pub quiz_type: Option<String>,
    pub notify_of_update: bool,
    pub time_limit: Option<i32>,
    pub published: Option<bool>,
}

#[derive(Deserialize)]
pub struct AddQuizRequest {
    pub course_id: String,
    pub module_id: String,
    pub quiz_id: String,
    pub title: Option<String>,
    pub position: Option<u32>,
    pub indent: Option<u32>,
    pub new_tab: Option<bool>,
}

#[derive(Deserialize)]
pub struct Quiz {
    pub title: Option<String>,
    pub quiz_id: Option<String>,
}

#[derive(Deserialize)]
pub struct GetQuestionRequest {
    pub course_id: String,
    pub quiz_id: String,
    pub question_id: String,
}

#[derive(Serialize, Deserialize)]
pub struct Answer {
    pub answer_text: String,
    pub answer_weight: u32,
    pub answer_comments: Option<String>,
}

#[derive(Deserialize)]
pub struct CreateQuestionRequest {
    pub course_id: String,
    pub quiz_id: String,
    pub name: String,
    pub text: String,
    pub question_type: Option<String>,
    pub points_possible: Option<f64>,
    pub answers: Vec<Answer>,
}

#[derive(Deserialize)]
pub struct UpdateQuestionRequest {
    pub course_id: String,
    pub quiz_id: String,
    pub question_id: String,
    pub name: Option<String>,
    pub text: Option<String>,
    pub question_type: Option<String>,
    pub points_possible: Option<f64>,
    pub answers: Option<Vec<Answer>>,
}
