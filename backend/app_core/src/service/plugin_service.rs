use crate::{
    CoreError,
    db::{UserPlugin, UserPluginConfig, UserPluginConfigDto},
    get_db_pool,
};

#[derive(Clone)]
pub struct PluginService;

impl PluginService {
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

    pub fn get_user_plugin_config(
        &self,
        user_id: i32,
        plugin_name: &str,
    ) -> Result<Option<UserPluginConfigDto>, CoreError> {
        let db_pool = get_db_pool();
        UserPluginConfig::get_user_plugin_config(db_pool, user_id, plugin_name)
    }
}
