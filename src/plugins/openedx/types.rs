use chrono::{DateTime, Local, Utc};
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
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxCreateCourseArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub org: String,
    pub number: String,
    pub run: String,
    pub title: String,
    pub pacing_type: Option<String>,
    pub team: Option<Vec<String>>,
}

#[derive(Deserialize, schemars::JsonSchema)]
pub struct OpenEdxListCourseRunsArgs {
    pub auth: OpenEdxAccessTokenPayload,
    pub page: Option<u32>,
    pub page_size: Option<u32>,
}
