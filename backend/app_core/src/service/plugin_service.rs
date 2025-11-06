use serde::{Deserialize, Serialize};

use crate::{
    ConfigType, CoreError, NewPlugin, NewPluginConfig, Plugin, PluginType,
    db::{PluginConfig, UserPlugin, UserPluginConfig, UserPluginConfigDto},
    get_db_pool,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginConfigSchema {
    pub config_key: String,
    pub config_type: ConfigType,
    pub description: Option<String>,
    pub is_required: bool,
    pub default_value: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    pub id: String,
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    #[serde(rename = "type")]
    pub plugin_type: PluginType,
    pub is_builtin: bool,
    pub created_by_user_id: Option<i32>,
    pub configs: Option<Vec<PluginConfigSchema>>,
}

#[derive(Clone)]
pub struct PluginService;

impl PluginService {
   
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
                    plugin_type: manifest.plugin_type.clone(),
                    is_builtin: manifest.is_builtin,
                    created_by_user_id: manifest.created_by_user_id,
                };
                Plugin::insert(new_plugin, db_pool)?
            }
        };

        if let Some(config_schema) = &manifest.configs {
            let plugin_configs: Vec<NewPluginConfig> = config_schema
                .iter()
                .map(|config| NewPluginConfig {
                    plugin_id: plugin.id,
                    config_key: config.config_key.clone(),
                    config_type: config.config_type.clone(),
                    description: config.description.clone(),
                    is_required: config.is_required,
                    is_secret: false,
                    default_value: config.default_value.clone(),
                })
                .collect();
            PluginConfig::insert(db_pool, plugin_configs)?;
        }

        Ok(plugin)
    }

    pub fn install_plugin_for_user(
        &self,
        user_id: i32,
        plugin_id: i32,
        config_values: Vec<(String, String)>,
    ) -> Result<i32, CoreError> {
        let db_pool = get_db_pool();
        UserPlugin::install_plugin_for_user(db_pool, user_id, plugin_id, config_values)
    }

    pub fn set_user_plugin_enabled(
        &self,
        user_id: i32,
        plugin_id: i32,
        is_enabled: bool,
    ) -> Result<(), CoreError> {
        let db_pool = get_db_pool();
        UserPlugin::set_user_plugin_enabled(db_pool, user_id, plugin_id, is_enabled)
    }

    pub fn get_user_plugin_with_configs(
        &self,
        plugin_id: i32,
    ) -> Result<UserPluginConfigDto, CoreError> {
        let db_pool = get_db_pool();
        UserPluginConfig::get_user_plugin_with_configs(db_pool, plugin_id)
    }

    pub fn get_user_plugins_with_config(
        &self,
        user_id: i32,
    ) -> Result<Vec<UserPluginConfigDto>, CoreError> {
        let db_pool = get_db_pool();
        UserPluginConfig::get_user_plugins_with_configs(db_pool, user_id)
    }
}
