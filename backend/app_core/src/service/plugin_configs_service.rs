// use serde::{Deserialize, Serialize};
// use serde_json::Value;

// use crate::{
//     CoreError, Plugin, PluginManifest,
//     db::{ConfigType, NewPluginConfig, PluginConfig, get_db_pool},
// };

// #[derive(Debug, Clone, Serialize, Deserialize)]
// pub struct ConfigProperty {
//     #[serde(rename = "type")]
//     pub property_type: ConfigType,
//     pub description: String,
//     #[serde(skip_serializing_if = "Option::is_none")]
//     pub default: Option<String>,
// }

// #[derive(Debug, Clone, Serialize, Deserialize)]
// pub struct PluginWithConfig {
//     #[serde(flatten)]
//     pub plugin: Plugin,
//     pub config: Vec<PluginConfig>,
//     pub config_schema: Option<Value>,
// }

// #[derive(Debug, Clone, Serialize, Deserialize)]
// pub struct ConfigSchema {
//     #[serde(rename = "type")]
//     pub schema_type: String,
//     pub properties: Vec<(String, ConfigProperty)>,
//     pub required: Vec<String>,
// }

// #[derive(Clone)]
// pub struct PluginConfigService;

// impl PluginConfigService {
//     pub fn insert_from_manifest(
//         &self,
//         manifest: PluginManifest,
//         is_builtin: bool,
//         created_by_user_id: Option<i32>,
//     ) -> Result<i32, CoreError> {
//         let db_pool = get_db_pool();
//         Ok(PluginConfig::insert(
//             &manifest,
//             is_builtin,
//             db_pool,
//             created_by_user_id,
//         )?)
//     }

//     pub fn get_list(&self) -> Result<Vec<PluginWithConfig>, CoreError> {
//         let db_pool = get_db_pool();

//         let plugins = Plugin::get_list(db_pool)?;
//         let mut result = Vec::new();

//         for plugin in plugins {
//             let config = PluginConfig::get_for_plugin(plugin.id, db_pool)?;
//             result.push(PluginWithConfig {
//                 plugin,
//                 config,
//                 config_schema: None,
//             });
//         }

//         Ok(result)
//     }

//     pub fn get_for_plugin(&self, plugin_id_val: i32) -> Result<Vec<PluginConfig>, CoreError> {
//         let db_pool = get_db_pool();
//         PluginConfig::get_for_plugin(plugin_id_val, db_pool)
//     }

//     pub fn update_configs(
//         &self,
//         plugin_id_val: i32,
//         configs: Vec<(String, String)>,
//     ) -> Result<PluginWithConfig, CoreError> {
//         let db_pool = get_db_pool();
//         PluginConfig::update_configs(plugin_id_val, configs, db_pool)?;

//         self.get_with_config(plugin_id_val)
//     }

//     pub fn get_with_config(&self, plugin_id: i32) -> Result<PluginWithConfig, CoreError> {
//         let db_pool = get_db_pool();
//         let plugin = Plugin::get(plugin_id, db_pool)?;
//         let config = PluginConfig::get_for_plugin(plugin_id, db_pool)?;

//         Ok(PluginWithConfig {
//             plugin,
//             config,
//             config_schema: None,
//         })
//     }

//     pub fn set_enabled(&self, plugin_id: i32, is_enabled: bool) -> Result<Plugin, CoreError> {
//         let db_pool = get_db_pool();
//         Plugin::set_enabled(plugin_id, is_enabled, db_pool)
//     }
// }
