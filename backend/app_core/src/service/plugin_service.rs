use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::{
    ConfigType, CoreError, NewPlugin, NewPluginConfig, Plugin, PluginType,
    db::{PluginConfig, UpsertUserPluginConfig, UserPluginConfig},
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

#[derive(Debug, Clone, Deserialize)]
pub struct NewUserConfigInput {
    pub config_key: String,
    pub config_value: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct UserPluginConfigDto {
    pub plugin_id: i32,
    pub plugin_name: String,
    pub version: String,
    pub description: Option<String>,
    pub enabled: bool,
    pub configs: Vec<UserPluginConfig>,
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

        if plugin.is_builtin {
            UserPluginConfig::install_builtin_for_all_users(plugin.id, db_pool)?;
        }

        Ok(plugin)
    }

    pub fn set_user_plugin_enabled(
        &self,
        user_id: i32,
        plugin_id: i32,
        is_enabled: bool,
    ) -> Result<usize, CoreError> {
        let db_pool = get_db_pool();
        UserPluginConfig::update_user_plugin_enabled(db_pool, user_id, plugin_id, is_enabled)
    }

    pub fn upsert_user_plugin_configs(
        &self,
        user_id: i32,
        plugin_id: i32,
        updates: Vec<NewUserConfigInput>,
    ) -> Result<usize, CoreError> {
        let records: Vec<UpsertUserPluginConfig> = updates
            .iter()
            .map(|u| UpsertUserPluginConfig {
                user_id,
                plugin_id,
                config_key: u.config_key.clone(),
                config_value: u.config_value.clone(),
            })
            .collect();

        let db_pool = get_db_pool();
        UserPluginConfig::upsert(records, db_pool)
    }

    pub fn get_user_plugin(
        &self,
        user_id: i32,
        plugin_id: i32,
    ) -> Result<UserPluginConfigDto, CoreError> {
        let db_pool = get_db_pool();

        let plugin = Plugin::get_plugin_for_user(user_id, plugin_id, db_pool)?;
        let configs = UserPluginConfig::get_user_configs_for_plugin(user_id, plugin_id, db_pool)?;

        let enabled = configs.iter().any(|config| config.enabled);

        Ok(UserPluginConfigDto {
            plugin_id: plugin.id,
            plugin_name: plugin.name,
            version: plugin.version,
            description: plugin.description,
            enabled,
            configs,
        })
    }

    pub fn get_user_plugins(&self, user_id: i32) -> Result<Vec<UserPluginConfigDto>, CoreError> {
        let db_pool = get_db_pool();

        let user_plugins = Plugin::get_list_for_user(user_id, db_pool)?;
        let plugin_ids: Vec<i32> = user_plugins.iter().map(|plugin| plugin.id).collect();

        let user_configs =
            UserPluginConfig::get_user_configs_for_plugins_list(user_id, plugin_ids, db_pool)?;

        let mut user_config_map: HashMap<i32, Vec<UserPluginConfig>> = user_configs
            .into_iter()
            .fold(HashMap::new(), |mut map, config| {
                map.entry(config.plugin_id).or_default().push(config);
                map
            });

        let results = user_plugins
            .into_iter()
            .map(|plugin| {
                let configs = user_config_map.remove(&plugin.id).unwrap_or_default();
                let enabled = configs.iter().any(|c| c.enabled);

                UserPluginConfigDto {
                    plugin_id: plugin.id,
                    plugin_name: plugin.name,
                    version: plugin.version,
                    description: plugin.description,
                    enabled,
                    configs,
                }
            })
            .collect();

        Ok(results)
    }
}
