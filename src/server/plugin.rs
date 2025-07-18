use super::filters::Filters;
use crate::{ToolRegistry, server::error::ConfigError};

pub trait Plugin: Send + Sync {
    fn name(&self) -> &str;
    fn register(&self, registrar: &mut PluginContext) -> Result<(), ConfigError>;
}

#[derive(Default)]
pub struct PluginContext {
    pub filters: Filters,
    pub tools: ToolRegistry,
}
