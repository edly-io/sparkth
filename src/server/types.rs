use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum CanvasResponse {
    Single(Value),
    Multiple(Vec<Value>),
}

#[derive(Deserialize)]
pub struct CourseParams {
    pub course_id: u32,
}

#[derive(Serialize, Deserialize)]
pub struct Course {
    pub name: String,
    course_code: Option<String>,
    sis_course_id: Option<u32>,
}

#[derive(Serialize, Deserialize)]
pub struct CoursePayload {
    pub course: Course,
    pub enroll_me: bool,
    pub account_id: u32,
}

#[derive(Deserialize)]
pub struct ModuleParams {
    pub course_id: u32,
    pub module_id: u32,
}

#[derive(Serialize, Deserialize)]
pub struct Module {
    name: String,
    position: Option<u8>,
    unlock_at: Option<DateTime<Utc>>,
    require_sequential_progress: Option<bool>,
    prerequisite_module_ids: Option<Vec<u32>>,
    publish_final_grade: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct ModulePayload {
    pub module: Module,
    pub course_id: u32,
}

#[derive(Serialize, Deserialize)]
pub struct UpdatedModule {
name: Option<String>,
position: Option<u8>,
unlock_at: Option<DateTime<Utc>>,
require_sequential_progress: Option<bool>,
prerequisite_module_ids: Option<Vec<u32>>,
publish_final_grade: Option<bool>,
published: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct UpdateModulePayload {
    pub module: UpdatedModule,
    pub course_id: u32,
    pub module_id: u32,
}

#[derive(Deserialize)]
pub struct ModuleItemParams {
    pub course_id: u32,
    pub module_id: u32,
    pub item_id: u32,
}

#[derive(Serialize, Deserialize)]
struct ModuleItemCompletionRequirement {
    requirement_type: String,
    min_score: Option<f64>,
}

#[derive(Serialize, Deserialize)]
enum ModuleItemType {
    File,
    Page,
    Discussion,
    Assignment,
    Quiz,
    SubHeader,
    ExternalUrl,
    ExternalTool,
}

#[derive(Serialize, Deserialize)]
pub struct ModuleItem {
title: String,
    #[serde(rename = "type")]
item_type: ModuleItemType,
content_id: Option<String>,
position: Option<u32>,
indent: Option<u32>,
page_url: Option<String>,
external_url: Option<String>,
new_tab: Option<bool>,
completion_requirement: Option<ModuleItemCompletionRequirement>,
}

#[derive(Serialize, Deserialize)]
pub struct ModuleItemPayload {
    pub module_id: u32,
    pub course_id: u32,
    pub module_item: ModuleItem,
}

#[derive(Serialize, Deserialize)]
pub struct UpdatedModuleItem {
    title: Option<String>,
    position: Option<u32>,
    indent: Option<u32>,
    external_url: Option<String>,
    new_tab: Option<bool>,
    completion_requirement: Option<ModuleItemCompletionRequirement>,
    module_id: Option<u32>,
    published: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct UpdateModuleItemPayload {
    pub module_id: u32,
    pub course_id: u32,
    pub item_id: u32,
    pub module_item: UpdatedModuleItem,
}

#[derive(Serialize, Deserialize)]
enum SortBy {
    #[serde(rename_all = "snake_case")]
    Title,
    #[serde(rename = "created_at")]
    CreatedAt,
    #[serde(rename = "updated_at")]
    UpdatedAt,
}

#[derive(Serialize, Deserialize)]enum Order {
    #[serde(rename = "asc")]
    Ascending,
    #[serde(rename = "desc")]
    Descending,
}

#[derive(Serialize, Deserialize)]
pub struct ListPagesPayload {
    pub course_id: u32,
    search_term: Option<String>,
    sort: Option<SortBy>,
    order: Option<Order>,
    published: Option<bool>,
    include: Option<Vec<String>>,
}

#[derive(Deserialize)]
pub struct PageParams {
    pub course_id: u32,
    pub page_url: String,
}

#[derive(Serialize, Deserialize, Default)]
enum EditingRoles {
    #[serde(rename_all = "lowercase")]
    #[default]
    Teachers,
    Students,
    Members,
    Public,
}

#[derive(Default, Serialize, Deserialize)]
struct Page {
    title: String,
    editing_roles: EditingRoles,
    body: Option<String>,
    notify_of_update: Option<bool>,
    published: Option<bool>,
    front_page: Option<bool>,
    publish_at: Option<DateTime<Utc>>,
}

#[derive(Serialize, Deserialize)]
pub struct PagePayload {
    pub course_id: u32,
    pub wiki_page: Page,
}

#[derive(Serialize, Deserialize)]
pub struct UpdatedPage {
    pub title: Option<String>,
    pub body: Option<String>,
    pub editing_roles: Option<EditingRoles>,
    pub notify_of_update: Option<bool>,
    pub published: Option<bool>,
    pub publish_at: Option<DateTime<Utc>>,
    pub front_page: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct UpdatePagePayload {
    pub course_id: u32,
    pub url_or_id: String,
    pub wiki_page: UpdatedPage,
}

#[derive(Deserialize)]
pub struct AddPageParams {
    pub course_id: u32,
    pub module_id: u32,
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
pub struct QuizParams {
    pub course_id: u32,
    pub quiz_id: u32,
}

#[derive(Serialize, Deserialize)]
pub enum QuizType {
    #[serde(rename_all = "snake_case")]
    Assignment,
    PracticeQuiz,
    GradedSurvey,
    Survey,
}

#[derive(Serialize, Deserialize)]
pub enum HideResults {
    #[serde(rename_all = "snake_case")]
    Always,
    UntilAfterLastAttempt,
}

#[derive(Serialize, Deserialize)]
pub enum ScoringPolicy {
    #[serde(rename_all = "snake_case")]
    KeepHighest,
    KeepLatest,
}

#[derive(Serialize, Deserialize)]
pub struct Quiz {
    pub title: String,
    pub description: String,
    pub quiz_type: QuizType,
    pub assignment_group_id: Option<i32>,
    pub time_limit: Option<i32>,
    pub shuffle_answers: Option<bool>,
    pub hide_results: Option<HideResults>,
    pub show_correct_answers: Option<bool>,
    pub show_correct_answers_last_attempt: Option<bool>,
    pub show_correct_answers_at: Option<DateTime<Utc>>,
    pub hide_correct_answers_at: Option<DateTime<Utc>>,
    pub allowed_attempts: Option<u8>,
    pub scoring_policy: Option<ScoringPolicy>,
    pub one_question_at_a_time: Option<bool>,
    pub cant_go_back: Option<bool>,
    pub access_code: Option<String>,
    pub ip_filter: Option<String>,
    pub due_at: Option<DateTime<Utc>>,
    pub lock_at: Option<DateTime<Utc>>,
    pub unlock_at: Option<DateTime<Utc>>,
    pub published: Option<bool>,
    pub one_time_results: Option<bool>,
    pub only_visible_to_overrides: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct QuizPayload {
    pub course_id: u32,
    pub quiz: Quiz,
}

#[derive(Serialize, Deserialize)]
pub struct UpdatedQuiz {
    pub title: Option<String>,
    pub description: Option<String>,
    pub quiz_type: Option<QuizType>,
    pub assignment_group_id: Option<i32>,
    pub time_limit: Option<i32>,
    pub shuffle_answers: Option<bool>,
    pub hide_results: Option<HideResults>,
    pub show_correct_answers: Option<bool>,
    pub show_correct_answers_last_attempt: Option<bool>,
    pub show_correct_answers_at: Option<DateTime<Utc>>,
    pub hide_correct_answers_at: Option<DateTime<Utc>>,
    pub allowed_attempts: Option<u8>,
    pub scoring_policy: Option<ScoringPolicy>,
    pub one_question_at_a_time: Option<bool>,
    pub cant_go_back: Option<bool>,
    pub access_code: Option<String>,
    pub ip_filter: Option<String>,
    pub due_at: Option<DateTime<Utc>>,
    pub lock_at: Option<DateTime<Utc>>,
    pub unlock_at: Option<DateTime<Utc>>,
    pub published: Option<bool>,
    pub one_time_results: Option<bool>,
    pub only_visible_to_overrides: Option<bool>,
    pub notify_of_update: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct UpdateQuizPayload {
    pub course_id: u32,
    pub quiz_id: u32,
    pub quiz: UpdatedQuiz,
}

#[derive(Serialize, Deserialize)]
pub struct AddQuizRequest {
    pub course_id: u32,
    pub module_id: u32,
    pub quiz_id: u32,
    pub title: Option<String>,
    pub position: Option<u32>,
    pub indent: Option<u32>,
    pub new_tab: Option<bool>,
}

// #[derive(Deserialize)]
// pub struct QuizParams {
//     pub title: Option<String>,
//     pub quiz_id: Option<String>,
// }

#[derive(Deserialize)]
pub struct QuestionParams {
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

#[derive(Serialize, Deserialize)]
pub enum QuestionType {
    #[serde(rename_all = "snake_case")]
    CalculatedQuestion,
    EssayQuestion,
    FileUploadQuestion,
    FillInMultipleBlanksQuestion,
    MatchingQuestion,
    MultipleAnswersQuestion,
    MultipleChoiceQuestion,
    MultipleDropdownsQuestion,
    NumericalQuestion,
    ShortAnswerQuestion,
    TextOnlyQuestion,
    TrueFalseQuestion,
}

#[derive(Serialize, Deserialize)]
pub struct Question {
    pub question_name: String,
    pub question_text: String,
    pub quiz_group_id: Option<u32>,
    pub question_type: Option<QuestionType>,
    pub position: Option<u8>,
    pub points_possible: Option<f64>,
    pub correct_comments: Option<String>,
    pub incorrect_comments: Option<String>,
    pub neutral_comments: Option<String>,
    pub text_after_answers: Option<String>,
    pub answers: Option<Vec<Answer>>,
}

#[derive(Serialize, Deserialize)]
pub struct QuestionPayload {
    pub question: Question,
    pub course_id: u32,
    pub quiz_id: u32,
}

#[derive(Serialize, Deserialize)]
pub struct UpdatedQuestion {
    pub question_name: Option<String>,
    pub question_text: Option<String>,
    pub quiz_group_id: Option<u32>,
    pub question_type: Option<QuestionType>,
    pub position: Option<u8>,
    pub points_possible: Option<f64>,
    pub correct_comments: Option<String>,
    pub incorrect_comments: Option<String>,
    pub neutral_comments: Option<String>,
    pub text_after_answers: Option<String>,
    pub answers: Option<Vec<Answer>>,
}

#[derive(Serialize, Deserialize)]
pub struct UpdateQuestionPayload {
    pub question: UpdatedQuestion,
    pub course_id: u32,
    pub quiz_id: u32,
    pub question_id: u32,
}

#[derive(Deserialize)]
pub struct ListUsersParams {
    pub account_id: String,
}

#[derive(Deserialize)]
pub struct CreateUserRequest {
    pub account_id: String,
    pub name: String,
    pub unique_id: String,
    pub short_name: Option<String>,
    pub sortable_name: Option<String>,
    pub send_confirmation: Option<bool>,
    pub communication_type: Option<String>,
    pub communication_address: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct User {
    pub name: String,
    pub terms_of_use: bool,
    pub skip_registration: bool,
    pub short_name: Option<String>,
    pub sortable_name: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct Pseudonym {
    pub unique_id: String,
    pub send_confirmation: Option<bool>,
}

#[derive(Serialize, Deserialize)]
pub struct UserPayload {
    pub account_id: String,
    pub user: User,
    pub pseudonym: Pseudonym,
}

#[derive(Serialize, Deserialize)]
pub enum EnrollmentType {
    StudentEnrollment,
    TeacherEnrollment,
    TaEnrollment,
    ObserverEnrollment,
    DesignerEnrollment,
}

#[derive(Serialize, Deserialize)]
pub enum EnrollmentState {
    #[serde(rename_all = "lowercase")]
    Active,
    Inactive,
    Invited,
}

#[derive(Serialize, Deserialize)]
pub struct Enrollment {
    pub user_id: u32,
    #[serde(rename = "type")]
    pub enrollment_type: EnrollmentType,
    pub start_at: Option<DateTime<Utc>>,
    pub end_at: Option<DateTime<Utc>>,
    pub role_id: Option<u32>,
    pub enrollment_state: Option<EnrollmentState>,
    pub course_section_id: Option<u32>,
    pub limit_privileges_to_course_section: Option<bool>,
    pub notify: Option<bool>,
    pub self_enrollment_code: Option<String>,
    pub self_enrolled: Option<bool>,
    pub associated_user_id: Option<u32>,
    pub sis_user_id: Option<String>,
    pub integration_id: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct EnrollmentPayload {
    pub course_id: u32,
    pub enrollment: Enrollment,
    pub root_account: Option<String>,
}
