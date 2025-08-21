use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum OpenEdxResponse {
    Single(Value),
    Multiple(Vec<Value>),
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxAuthenticationPayload {
    pub lms_url: String,
    pub studio_url: String,
    pub username: String,
    pub password: String,
}
#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxAccessTokenPayload {
    pub access_token: String,
    pub lms_url: String,
    pub studio_url: String,
}

#[derive(Serialize, Deserialize, schemars::JsonSchema)]
pub struct CourseArgs {
    pub org: String,
    pub number: String,
    pub run: String,
    pub title: String,
    pub pacing_type: String,
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxCreateCourseArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub course: CourseArgs,
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxListCourseRunsArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub page: Option<u32>,
    pub page_size: Option<u32>,
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxRootUsageKeyArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub course_id: String,
}

#[derive(Serialize, Deserialize, schemars::JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum XBlockCategory {
    Chapter,
    Sequential,
    Vertical,
}

#[derive(Serialize, Deserialize, schemars::JsonSchema)]
pub struct OpenEdxCreateXBlock {
    parent_locator: String,
    category: XBlockCategory,
    display_name: String,
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxXBlockPayload {
    pub auth: OpenEdxAccessTokenPayload,
    pub xblock: OpenEdxCreateXBlock,
    pub course_id: String,
}
