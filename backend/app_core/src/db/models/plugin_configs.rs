use chrono::NaiveDateTime;
use diesel::{
    ExpressionMethods, OptionalExtension, RunQueryDsl, Selectable, SelectableHelper,
    prelude::{Associations, Identifiable, Insertable, Queryable},
    query_dsl::methods::{FilterDsl, SelectDsl},
};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    CoreError,
    db::{DbPool, Plugin},
    schema::plugin_configs,
};

#[derive(
    Debug, Deserialize, Clone, Queryable, Selectable, Serialize, Identifiable, Associations,
)]
#[diesel(belongs_to(Plugin))]
#[diesel(table_name = plugin_configs)]
#[diesel(primary_key(id))]
#[diesel(check_for_backend(diesel::pg::Pg))]
pub struct PluginConfig {
    pub id: i32,
    pub plugin_id: i32,
    pub config_key: String,
    pub config_value: Option<String>,
    pub is_secret: bool,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

#[derive(Debug, Insertable, Serialize, Deserialize)]
#[diesel(table_name = plugin_configs)]
pub struct NewPluginConfig {
    pub plugin_id: i32,
    pub config_key: String,
    pub config_value: Option<String>,
    pub is_secret: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginWithConfig {
    #[serde(flatten)]
    pub plugin: Plugin,
    pub config: Vec<(String, String)>,
    pub config_schema: Option<Value>,
}

impl PluginConfig {
    pub fn insert(config: NewPluginConfig, db_pool: &DbPool) -> Result<(), CoreError> {
        use crate::schema::plugin_configs::dsl::*;

        let conn = &mut db_pool.get()?;
        diesel::insert_into(plugin_configs)
            .values(&config)
            .on_conflict((plugin_id, config_key))
            .do_update()
            .set(config_value.eq(&config.config_value))
            .execute(conn)?;

        Ok(())
    }

    pub fn get(db_pool: &DbPool, key: &str) -> Result<Option<PluginConfig>, CoreError> {
        use crate::schema::plugin_configs::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(plugin_configs
            .filter(plugin_id.eq(plugin_id))
            .filter(config_key.eq(key))
            .select(PluginConfig::as_select())
            .first::<PluginConfig>(conn)
            .optional()?)
    }

    pub fn get_for_plugin(
        plugin_id_val: i32,
        db_pool: &DbPool,
    ) -> Result<Vec<PluginConfig>, CoreError> {
        use crate::schema::plugin_configs::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(plugin_configs
            .filter(plugin_id.eq(plugin_id_val))
            .select(PluginConfig::as_select())
            .load::<PluginConfig>(conn)?)
    }

    pub fn update_configs(
        plugin_id_val: i32,
        configs: Vec<(String, String)>,
        db_pool: &DbPool,
    ) -> Result<(), CoreError> {
        for (key, value) in configs {
            let new_config = NewPluginConfig {
                plugin_id: plugin_id_val,
                config_key: key.clone(),
                config_value: Some(value),
                is_secret: Self::is_secret_key(&key),
            };
            Self::insert(new_config, db_pool)?;
        }
        Ok(())
    }

    pub fn is_secret_key(key: &str) -> bool {
        let secret_keywords = ["password", "token", "secret", "api_key", "private_key"];
        let key_lower = key.to_lowercase();
        secret_keywords.iter().any(|&kw| key_lower.contains(kw))
    }
}
