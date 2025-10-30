use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    CoreError, Plugin,
    db::{NewPluginConfig, PluginConfig, get_db_pool},
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigProperty {
    #[serde(rename = "type")]
    pub property_type: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginWithConfig {
    #[serde(flatten)]
    pub plugin: Plugin,
    pub config: Vec<PluginConfig>,
    pub config_schema: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigSchema {
    #[serde(rename = "type")]
    pub schema_type: String,
    pub properties: Vec<(String, ConfigProperty)>,
    pub required: Vec<String>,
}

#[derive(Clone)]
pub struct PluginConfigService;

impl PluginConfigService {
    pub fn insert(&self, plugin_id: i32, config_schema: &ConfigSchema) -> Result<(), CoreError> {
        let db_pool = get_db_pool();

        println!("existing {:?}", config_schema);

        for (key, property) in &config_schema.properties {
            let existing = PluginConfig::get(db_pool, key)?;

            if existing.is_none() {
                let new_config = NewPluginConfig {
                    plugin_id,
                    config_key: key.clone(),
                    config_value: property.default.clone(),
                    is_secret: PluginConfig::is_secret_key(key),
                };

                PluginConfig::insert(new_config, db_pool)?;
            }
        }

        Ok(())
    }

    pub fn get_list(&self) -> Result<Vec<PluginWithConfig>, CoreError> {
        let db_pool = get_db_pool();

        let plugins = Plugin::get_list(db_pool)?;
        let mut result = Vec::new();

        for plugin in plugins {
            let config = PluginConfig::get_for_plugin(plugin.id, db_pool)?;
            result.push(PluginWithConfig {
                plugin,
                config,
                config_schema: None,
            });
        }

        Ok(result)
    }

    pub fn get_for_plugin(&self, plugin_id_val: i32) -> Result<Vec<PluginConfig>, CoreError> {
        let db_pool = get_db_pool();
        PluginConfig::get_for_plugin(plugin_id_val, db_pool)
    }

    pub fn update_configs(
        &self,
        plugin_id_val: i32,
        configs: Vec<(String, String)>,
    ) -> Result<PluginWithConfig, CoreError> {
        let db_pool = get_db_pool();
        PluginConfig::update_configs(plugin_id_val, configs, db_pool)?;

        self.get_with_config(plugin_id_val)
    }

    pub fn get_with_config(&self, plugin_id: i32) -> Result<PluginWithConfig, CoreError> {
        let db_pool = get_db_pool();
        let plugin = Plugin::get(plugin_id, db_pool)?;
        let config = PluginConfig::get_for_plugin(plugin_id, db_pool)?;

        Ok(PluginWithConfig {
            plugin,
            config,
            config_schema: None,
        })
    }

    pub fn set_enabled(&self, plugin_id: i32, is_enabled: bool) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        Plugin::set_enabled(plugin_id, is_enabled, db_pool)
    }
}
