use crate::plugin::error::Result;

use super::MCPPlugin;
use app_core::{Plugin, PluginManifest, PluginService};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct PluginRegistry {
    plugins: Arc<RwLock<HashMap<String, Box<dyn MCPPlugin>>>>,
}

impl PluginRegistry {
    pub fn new() -> Self {
        Self {
            plugins: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn register(&self, plugin: Box<dyn MCPPlugin>) -> Result<()> {
        let manifest = plugin.complete_manifest();
        let plugin_id = manifest.id.clone();
        self.register_in_db(&manifest)?;
        let mut plugins = self.plugins.write().await;
        plugins.insert(plugin_id, plugin);
        Ok(())
    }

    fn register_in_db(&self, manifest: &PluginManifest) -> Result<Plugin> {
        let plugin_service = PluginService;
        Ok(plugin_service.insert_from_manifest(manifest)?)
    }
}
