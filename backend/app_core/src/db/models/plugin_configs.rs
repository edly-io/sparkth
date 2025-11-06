use chrono::NaiveDateTime;
use diesel::{
    ExpressionMethods, OptionalExtension, PgConnection, RunQueryDsl, Selectable, SelectableHelper,
    prelude::{Associations, Identifiable, Insertable, Queryable},
    query_dsl::methods::{FilterDsl, SelectDsl},
    r2d2::{ConnectionManager, PooledConnection},
};
use serde::{Deserialize, Serialize};

use crate::{CoreError, DbPool, db::Plugin, schema::plugin_config_schema};

#[derive(Debug, Clone, Serialize, Deserialize, diesel_derive_enum::DbEnum)]
#[ExistingTypePath = "crate::schema::sql_types::ConfigTypeEnum"]
#[serde(rename_all = "lowercase")]
pub enum ConfigType {
    String,
    Number,
    Boolean,
    JSON,
    Url,
    Email,
    Password,
}

#[derive(
    Debug, Deserialize, Clone, Queryable, Selectable, Serialize, Identifiable, Associations,
)]
#[diesel(belongs_to(Plugin))]
#[diesel(table_name = plugin_config_schema)]
#[diesel(primary_key(id))]
#[diesel(check_for_backend(diesel::pg::Pg))]
pub struct PluginConfig {
    pub id: i32,
    pub plugin_id: i32,
    pub config_key: String,
    pub config_type: ConfigType,
    pub description: Option<String>,
    pub is_required: bool,
    pub is_secret: bool,
    pub default_value: Option<String>,
    pub created_at: NaiveDateTime,
}

#[derive(Debug, Clone, Insertable, Serialize, Deserialize)]
#[diesel(table_name = plugin_config_schema)]
pub struct NewPluginConfig {
    pub plugin_id: i32,
    pub config_key: String,
    pub config_type: ConfigType,
    pub description: Option<String>,
    pub is_required: bool,
    pub is_secret: bool,
    pub default_value: Option<String>,
}

impl PluginConfig {
    pub fn insert(db_pool: &DbPool, configs: Vec<NewPluginConfig>) -> Result<usize, CoreError> {
        use crate::schema::plugin_config_schema::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(diesel::insert_into(plugin_config_schema)
            .values(configs)
            .execute(conn)?)
    }

    pub fn get(db_pool: &DbPool, key: &str) -> Result<Option<PluginConfig>, CoreError> {
        use crate::schema::plugin_config_schema::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(plugin_config_schema
            .filter(plugin_id.eq(plugin_id))
            .filter(config_key.eq(key))
            .select(PluginConfig::as_select())
            .first::<PluginConfig>(conn)
            .optional()?)
    }

    // fn is_secret_key(key: &str) -> bool {
    //     let secret_keywords = ["password", "token", "secret", "api_key", "private_key"];
    //     let key_lower = key.to_lowercase();
    //     secret_keywords.iter().any(|&kw| key_lower.contains(kw))
    // }

    pub fn get_plugin_config_schema(
        p_id: i32,
        conn: &mut PooledConnection<ConnectionManager<PgConnection>>,
    ) -> Result<Vec<(String, bool, Option<String>)>, CoreError> {
        use crate::schema::plugin_config_schema::dsl::*;

        Ok(plugin_config_schema
            .filter(plugin_id.eq(p_id))
            .select((config_key, is_required, default_value))
            .load::<(String, bool, Option<String>)>(conn)?)
    }
}
