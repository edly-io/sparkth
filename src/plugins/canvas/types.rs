use serde::Deserialize;

#[derive(Deserialize)]
pub struct GetCourseRequest {
    pub course_id: String,
}

#[derive(Deserialize)]
pub struct CourseCreationRequest {
    account_id: String,
    name: String,
    course_code: Option<String>,
    sis_course_id: Option<String>,
}
