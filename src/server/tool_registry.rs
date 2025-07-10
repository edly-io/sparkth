use rmcp::model::CallToolResult;
use serde_json::Value;

use crate::server::tool::{Tool, ToolError};

pub struct ToolRegistry {
    tools: Vec<Box<dyn Tool>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self { tools: Vec::new() }
    }

    pub fn register(&mut self, tool: Box<dyn Tool>) -> &mut Self {
        self.tools.push(tool);
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
        return None;
    }
}
