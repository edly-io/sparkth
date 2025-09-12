use schemars::JsonSchema;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxAuth {
    pub lms_url: String,
    pub studio_url: String,
    pub username: String,
    pub password: String,
}

#[derive(Deserialize, Serialize)]
pub struct TokenResponse {
    pub access_token: String,
    pub refresh_token: Option<String>,
    token_type: Option<String>,
    expires_in: Option<u64>,
    scope: Option<String>,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxLMSAccess {
    pub access_token: String,
    pub lms_url: String,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxAccessTokenPayload {
    pub access_token: String,
    pub lms_url: String,
    pub studio_url: String,
}

#[derive(serde::Deserialize, schemars::JsonSchema)]
pub struct OpenEdxRefreshTokenPayload {
    pub lms_url: String,
    pub studio_url: String,
    pub refresh_token: String,
}

#[derive(Serialize, Deserialize, JsonSchema)]
pub struct CourseArgs {
    pub org: String,
    pub number: String,
    pub run: String,
    pub title: String,
    pub pacing_type: String,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxCreateCourseArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub course: CourseArgs,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxListCourseRunsArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub page: Option<u32>,
    pub page_size: Option<u32>,
}

#[derive(Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum XBlockCategory {
    Chapter,
    Sequential,
    Vertical,
}

#[derive(Serialize, Deserialize, JsonSchema)]
pub struct OpenEdxCreateXBlock {
    #[schemars(
        description = "The parent locator for course should be in the format `block-v1:ORG+COURSE+RUN+type@course+block@course`"
    )]
    parent_locator: String,
    category: XBlockCategory,
    display_name: String,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxXBlockPayload {
    pub auth: OpenEdxAccessTokenPayload,
    pub xblock: OpenEdxCreateXBlock,
    pub course_id: String,
}

#[derive(Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum Component {
    Problem,
    Html,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxCreateProblemOrHtmlArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub course_id: String,
    pub unit_locator: String,
    pub kind: Option<Component>,
    pub display_name: Option<String>,
    pub data: Option<String>,
    pub metadata: Option<Value>,
    pub mcq_boilerplate: Option<bool>,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxCourseTreeRequest {
    pub auth: OpenEdxAccessTokenPayload,
    pub course_id: String,
}

#[derive(Deserialize, JsonSchema)]
pub struct OpenEdxUpdateXBlockPayload {
    pub auth: OpenEdxAccessTokenPayload,
    pub course_id: String,
    pub locator: String,
    pub data: Option<String>,
    #[serde(default, deserialize_with = "deserialize_metadata_option")]
    pub metadata: Option<Value>,
}

#[derive(serde::Deserialize, schemars::JsonSchema)]
pub struct OpenEdxGetBlockContentArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub course_id: String,
    pub locator: String,
}


pub fn deserialize_metadata_option<'de, D>(deserializer: D) -> Result<Option<Value>, D::Error>
where
    D: Deserializer<'de>,
{
    let opt: Option<Value> = Option::deserialize(deserializer)?;
    match opt {
        Some(Value::String(s)) => serde_json::from_str(&s)
            .map(Some)
            .map_err(serde::de::Error::custom),
        other => Ok(other),
    }
}
