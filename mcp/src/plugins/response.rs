use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Deserialize)]
pub enum LMSResponse {
    Single(Value),
    Multiple(Vec<Value>),
}
