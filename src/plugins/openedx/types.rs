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