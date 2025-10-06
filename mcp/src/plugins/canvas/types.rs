use chrono::{DateTime, Local, Utc};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Deserialize, JsonSchema, Clone, Debug, Serialize)]
pub struct AuthenticationPayload {
    pub api_url: String,
    pub api_token: String,
}

#[derive(Deserialize, JsonSchema)]
pub struct CourseParams {
    pub course_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum CourseFormat {
    OnCampus,
    Online,
    Blended,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct Course {
    pub name: String,
    course_code: Option<String>,
    sis_course_id: Option<u32>,
    start_at: Option<DateTime<Local>>,
    end_at: Option<DateTime<Local>>,
    is_public: Option<bool>,
    course_format: Option<CourseFormat>,
    post_manually: Option<bool>,
}

#[derive(JsonSchema, Deserialize, Serialize)]
pub struct CoursePayload {
    course: Course,
    enroll_me: bool,
    offer: Option<bool>,
    enable_sis_reactivation: Option<bool>,
    pub account_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(Deserialize, JsonSchema)]
pub struct ModuleParams {
    pub course_id: u32,
    pub module_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct Module {
    name: String,
    position: Option<u8>,
    unlock_at: Option<DateTime<Utc>>,
    require_sequential_progress: Option<bool>,
    prerequisite_module_ids: Option<Vec<u32>>,
    publish_final_grade: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct ModulePayload {
    module: Module,
    pub course_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct UpdatedModule {
    name: Option<String>,
    position: Option<u8>,
    unlock_at: Option<DateTime<Utc>>,
    require_sequential_progress: Option<bool>,
    prerequisite_module_ids: Option<Vec<u32>>,
    publish_final_grade: Option<bool>,
    published: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct UpdateModulePayload {
    module: UpdatedModule,
    pub course_id: u32,
    pub module_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Deserialize)]
pub struct ModuleItemParams {
    pub course_id: u32,
    pub module_id: u32,
    pub item_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct ModuleItemCompletionRequirement {
    requirement_type: String,
    min_score: Option<f64>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
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

#[derive(JsonSchema, Serialize, Deserialize)]
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

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct ModuleItemPayload {
    pub module_id: u32,
    pub course_id: u32,
    module_item: ModuleItem,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct UpdatedModuleItem {
    title: Option<String>,
    position: Option<u32>,
    indent: Option<u32>,
    external_url: Option<String>,
    new_tab: Option<bool>,
    completion_requirement: Option<ModuleItemCompletionRequirement>,
    module_id: Option<u32>,
    published: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct UpdateModuleItemPayload {
    pub module_id: u32,
    pub course_id: u32,
    pub item_id: u32,
    module_item: UpdatedModuleItem,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum SortBy {
    Title,
    CreatedAt,
    UpdatedAt,
}

#[derive(JsonSchema, Serialize, Deserialize)]
enum Order {
    #[serde(rename = "asc")]
    Ascending,
    #[serde(rename = "desc")]
    Descending,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct ListPagesPayload {
    pub auth: AuthenticationPayload,
    pub course_id: u32,
    search_term: Option<String>,
    sort: Option<SortBy>,
    order: Option<Order>,
    published: Option<bool>,
    include: Option<Vec<String>>,
}

#[derive(JsonSchema, Deserialize)]
pub struct PageParams {
    pub course_id: u32,
    pub page_url: String,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
enum EditingRoles {
    #[default]
    Teachers,
    Students,
    Members,
    Public,
}

#[derive(JsonSchema, Default, Serialize, Deserialize)]
struct Page {
    title: String,
    editing_roles: EditingRoles,
    body: Option<String>,
    notify_of_update: Option<bool>,
    published: Option<bool>,
    front_page: Option<bool>,
    publish_at: Option<DateTime<Utc>>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct PagePayload {
    pub auth: AuthenticationPayload,
    pub course_id: u32,
    wiki_page: Page,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct UpdatedPage {
    title: Option<String>,
    body: Option<String>,
    editing_roles: Option<EditingRoles>,
    notify_of_update: Option<bool>,
    published: Option<bool>,
    publish_at: Option<DateTime<Utc>>,
    front_page: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct UpdatePagePayload {
    pub auth: AuthenticationPayload,
    pub course_id: u32,
    pub url_or_id: String,
    wiki_page: UpdatedPage,
}

#[derive(JsonSchema, Deserialize)]
pub struct QuizParams {
    pub course_id: u32,
    pub quiz_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum QuizType {
    Assignment,
    PracticeQuiz,
    GradedSurvey,
    Survey,
}

#[derive(JsonSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum HideResults {
    Always,
    UntilAfterLastAttempt,
}

#[derive(JsonSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum ScoringPolicy {
    KeepHighest,
    KeepLatest,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct Quiz {
    title: String,
    pub description: String,
    quiz_type: QuizType,
    assignment_group_id: Option<i32>,
    time_limit: Option<i32>,
    shuffle_answers: Option<bool>,
    hide_results: Option<HideResults>,
    show_correct_answers: Option<bool>,
    show_correct_answers_last_attempt: Option<bool>,
    show_correct_answers_at: Option<DateTime<Utc>>,
    hide_correct_answers_at: Option<DateTime<Utc>>,
    allowed_attempts: Option<u8>,
    scoring_policy: Option<ScoringPolicy>,
    one_question_at_a_time: Option<bool>,
    cant_go_back: Option<bool>,
    access_code: Option<String>,
    ip_filter: Option<String>,
    due_at: Option<DateTime<Utc>>,
    lock_at: Option<DateTime<Utc>>,
    unlock_at: Option<DateTime<Utc>>,
    published: Option<bool>,
    one_time_results: Option<bool>,
    only_visible_to_overrides: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct QuizPayload {
    pub auth: AuthenticationPayload,
    pub course_id: u32,
    quiz: Quiz,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct UpdatedQuiz {
    title: Option<String>,
    description: Option<String>,
    quiz_type: Option<QuizType>,
    assignment_group_id: Option<i32>,
    time_limit: Option<i32>,
    shuffle_answers: Option<bool>,
    hide_results: Option<HideResults>,
    show_correct_answers: Option<bool>,
    show_correct_answers_last_attempt: Option<bool>,
    show_correct_answers_at: Option<DateTime<Utc>>,
    hide_correct_answers_at: Option<DateTime<Utc>>,
    allowed_attempts: Option<u8>,
    scoring_policy: Option<ScoringPolicy>,
    one_question_at_a_time: Option<bool>,
    cant_go_back: Option<bool>,
    access_code: Option<String>,
    ip_filter: Option<String>,
    due_at: Option<DateTime<Utc>>,
    lock_at: Option<DateTime<Utc>>,
    unlock_at: Option<DateTime<Utc>>,
    published: Option<bool>,
    one_time_results: Option<bool>,
    only_visible_to_overrides: Option<bool>,
    notify_of_update: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct UpdateQuizPayload {
    pub auth: AuthenticationPayload,
    pub course_id: u32,
    pub quiz_id: u32,
    quiz: UpdatedQuiz,
}

#[derive(JsonSchema, Deserialize)]
pub struct QuestionParams {
    pub course_id: String,
    pub quiz_id: String,
    pub question_id: String,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct Answer {
    answer_text: String,
    answer_weight: u32,
    answer_comments: Option<String>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
enum QuestionType {
    #[serde(rename = "calculated_question")]
    Calculated,
    #[serde(rename = "fill_in_multiple_blanks_question")]
    FillInMultipleBlanks,
    #[serde(rename = "multiple_choice_question")]
    MultipleChoice,
    #[serde(rename = "text_only_question")]
    TextOnly,
    #[serde(rename = "true_false_question")]
    TrueFalse,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct Question {
    question_name: String,
    question_text: String,
    quiz_group_id: Option<u32>,
    question_type: Option<QuestionType>,
    position: Option<u8>,
    points_possible: Option<f64>,
    correct_comments: Option<String>,
    incorrect_comments: Option<String>,
    neutral_comments: Option<String>,
    text_after_answers: Option<String>,
    answers: Option<Vec<Answer>>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct QuestionPayload {
    question: Question,
    pub course_id: u32,
    pub quiz_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct UpdatedQuestion {
    question_name: Option<String>,
    question_text: Option<String>,
    quiz_group_id: Option<u32>,
    question_type: Option<QuestionType>,
    position: Option<u8>,
    points_possible: Option<f64>,
    correct_comments: Option<String>,
    incorrect_comments: Option<String>,
    neutral_comments: Option<String>,
    text_after_answers: Option<String>,
    answers: Option<Vec<Answer>>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct UpdateQuestionPayload {
    question: UpdatedQuestion,
    pub course_id: u32,
    pub quiz_id: u32,
    pub question_id: u32,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
struct User {
    name: String,
    terms_of_use: bool,
    skip_registration: bool,
    short_name: Option<String>,
    sortable_name: Option<String>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct Pseudonym {
    pub unique_id: String,
    send_confirmation: Option<bool>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct UserPayload {
    pub account_id: String,
    user: User,
    pub pseudonym: Pseudonym,
    pub auth: AuthenticationPayload,
}

#[derive(JsonSchema, Serialize, Deserialize)]
enum EnrollmentType {
    #[serde(rename = "StudentEnrollment")]
    Student,
    #[serde(rename = "TeacherEnrollment")]
    Teacher,
    #[serde(rename = "TaEnrollment")]
    Ta,
    #[serde(rename = "ObserverEnrollment")]
    Observer,
    #[serde(rename = "DesignerEnrollment")]
    Designer,
}

#[derive(JsonSchema, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum EnrollmentState {
    Active,
    Inactive,
    Invited,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct Enrollment {
    pub user_id: u32,
    #[serde(rename = "type")]
    enrollment_type: EnrollmentType,
    start_at: Option<DateTime<Utc>>,
    end_at: Option<DateTime<Utc>>,
    role_id: Option<u32>,
    enrollment_state: Option<EnrollmentState>,
    course_section_id: Option<u32>,
    limit_privileges_to_course_section: Option<bool>,
    notify: Option<bool>,
    self_enrollment_code: Option<String>,
    self_enrolled: Option<bool>,
    associated_user_id: Option<u32>,
    sis_user_id: Option<String>,
    integration_id: Option<String>,
}

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct EnrollmentPayload {
    pub course_id: u32,
    pub enrollment: Enrollment,
    pub root_account: Option<String>,
    pub auth: AuthenticationPayload,
}
