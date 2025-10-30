use crate::{
    CoreError, PluginConfigService,
    db::{NewPlugin, Plugin, PluginManifest, get_db_pool},
};

#[derive(Clone)]
pub struct PluginService;

impl PluginService {
    pub fn insert(&self, plugin: NewPlugin) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        Plugin::insert(plugin, db_pool)
    }

    pub fn insert_from_manifest(&self, manifest: &PluginManifest) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        let existing = Plugin::get_by_name(manifest.id.clone(), db_pool)?;

        let plugin = match existing {
            Some(plugin) if plugin.version != manifest.version => {
                Plugin::update_version(plugin.id, manifest, db_pool)?
            }
            Some(plugin) => plugin,
            None => {
                let new_plugin = NewPlugin {
                    name: manifest.id.clone(),
                    version: manifest.version.clone(),
                    description: manifest.description.clone(),
                    enabled: true,
                    plugin_type: format!("{:?}", manifest.plugin_type).to_lowercase(),
                };
                self.insert(new_plugin)?
            }
        };

        if let Some(config_schema) = &manifest.config_schema {
            let service = PluginConfigService;
            service.insert(plugin.id, config_schema)?;
        }

        Ok(plugin)
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
