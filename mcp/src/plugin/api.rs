use app_core::PluginManifest;

pub trait MCPPlugin: Send + Sync {
    fn manifest(&self) -> &PluginManifest;
    fn complete_manifest(&self) -> PluginManifest {
        self.manifest().clone()
    }
}
