use async_trait::async_trait;
use rmcp::model::{CallToolResult, ErrorCode};
use serde_json::Value;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ToolError {
    #[error("Tool '{name}' is missing required arguments: {args}")]
    MissingArgs { name: String, args: String },
    #[error("Tool '{name}' received invalid arguments. Expected: {args}")]
    InvalidArgs { name: String, args: String },
    #[error("Failed to perform operation. Error code: {error_code:?}, message: {message}")]
    InternalError {
        error_code: ErrorCode,
        message: String,
    },
}

#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    async fn call(&self, args: Option<Value>) -> Result<CallToolResult, ToolError>;
}
