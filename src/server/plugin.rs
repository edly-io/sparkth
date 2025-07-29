use super::filters::Filters;
use crate::server::error::ConfigError;

// TODO: Add plugins for different LMSs/Learning environments

trait Plugin: Send + Sync {
    fn name(&self) -> &str;
    fn register(&self, registrar: &mut PluginContext) -> Result<(), ConfigError>;
}

#[derive(Default)]
pub struct PluginContext {
    pub _filters: Filters,
}
