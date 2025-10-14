use crate::db::{
    db_pool::get_db_pool,
    error::CoreError,
    models::plugin::{NewPlugin, Plugin},
};

pub struct PluginService;

impl PluginService {
    pub fn insert(&self, plugin: NewPlugin) -> Result<Plugin, CoreError> {
        let db_pool = get_db_pool();
        Plugin::insert(plugin, db_pool)
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
