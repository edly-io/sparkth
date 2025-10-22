use crate::{CoreError, NewPlugin, Plugin, PluginManifest, get_db_pool};

#[derive(Clone)]
pub struct PluginService;

impl PluginService {
    pub fn insert(&self, plugin: NewPlugin) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        Plugin::insert(plugin, db_pool)
    }

    pub fn insert_from_manifest(&self, manifest: &PluginManifest) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        Plugin::insert_from_manifest(manifest, db_pool)
    }

    pub fn get(&self, id: i32) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        Plugin::get(id, db_pool)
    }

    pub fn get_list(&self) -> Result<Vec<Plugin>, CoreError> {
        let db_pool = get_db_pool();
        Plugin::get_list(db_pool)
    }
}
