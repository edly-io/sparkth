use std::sync::Arc;

use rmcp::model::CallToolResult;
use serde_json::Value;

use crate::server::tool_trait::{Tool, ToolError};

#[derive(Default, Clone)]
pub struct ToolRegistry {
    tools: Vec<Arc<dyn Tool>>,
}

impl ToolRegistry {
    pub fn register<T: Tool + 'static>(&mut self, tool: T) -> &mut Self {
        self.tools.push(Arc::new(tool));
        self
    }

    pub fn list_tools(&self) -> Vec<String> {
        self.tools
            .iter()
            .map(|tool| tool.name().to_owned())
            .collect()
    }

    pub async fn call(
        &self,
        name: &str,
        args: Option<Value>,
    ) -> Option<Result<CallToolResult, ToolError>> {
        for tool in &self.tools {
            if tool.name() == name {
                return Some(tool.call(args).await);
            }
        }
        None
    }
}
