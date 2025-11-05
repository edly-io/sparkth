use app_core::{ConfigSchema, PluginType};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    pub id: String,
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    #[serde(rename = "type")]
    pub plugin_type: PluginType,
    pub config_schema: Option<ConfigSchema>,
    pub authors: Vec<String>,
}

pub trait MCPPlugin: Send + Sync {
    fn manifest(&self) -> &PluginManifest;
    fn complete_manifest(&self) -> PluginManifest {
        self.manifest().clone()
    }
}
