use chrono::NaiveDateTime;
use diesel::{
    ExpressionMethods, OptionalExtension, RunQueryDsl, Selectable, SelectableHelper,
    prelude::{Associations, Identifiable, Insertable, Queryable},
    query_dsl::methods::{FilterDsl, SelectDsl},
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
            .on_conflict((plugin_id, config_key))
            .do_nothing()
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

    pub fn get_config_list_for_plugins(
        plugin_ids: &Vec<i32>,
        db_pool: &DbPool,
    ) -> Result<Vec<PluginConfig>, CoreError> {
        use crate::schema::plugin_config_schema::dsl::{plugin_config_schema, plugin_id};

        let conn = &mut db_pool.get()?;

        let schema_list = plugin_config_schema
            .filter(plugin_id.eq_any(plugin_ids))
            .load(conn)?;
        Ok(schema_list)
    }

    pub fn get_plugin_config_schema(
        p_id: i32,
        db_pool: &DbPool,
    ) -> Result<Vec<PluginConfig>, CoreError> {
        use crate::schema::plugin_config_schema::dsl::{plugin_config_schema, plugin_id};

        let conn = &mut db_pool.get()?;

        Ok(plugin_config_schema.filter(plugin_id.eq(p_id)).load(conn)?)
    }
}
