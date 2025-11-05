use chrono::NaiveDateTime;
use diesel::{
    ExpressionMethods, PgConnection, RunQueryDsl, Selectable,
    prelude::{Associations, Identifiable, Insertable, Queryable},
    query_dsl::methods::{FilterDsl, SelectDsl},
    r2d2::{ConnectionManager, PooledConnection},
};
use serde::{Deserialize, Serialize};

use crate::{CoreError, db::Plugin, schema::plugin_config_schema};

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

#[derive(Debug, Insertable, Serialize, Deserialize)]
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigProperty {
    #[serde(rename = "type")]
    pub property_type: ConfigType,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigSchema {
    #[serde(rename = "type")]
    pub schema_type: String,
    pub properties: Vec<(String, ConfigProperty)>,
    pub required: Vec<String>,
}

// #[derive(Debug, Clone, Serialize, Deserialize)]
// pub struct PluginManifest {
//     pub id: String,
//     pub name: String,
//     pub version: String,
//     pub description: Option<String>,
//     #[serde(rename = "type")]
//     pub plugin_type: PluginType,
//     pub config_schema: Option<ConfigSchema>,
//     pub authors: Vec<String>,
// }

impl PluginConfig {
    // pub fn insert(
    //     manifest: &PluginManifest,
    //     is_builtin: bool,
    //     db_pool: &DbPool,
    //     created_by_user_id: Option<i32>,
    // ) -> Result<i32, CoreError> {
    //     use crate::schema::plugin_config_schema::dsl::*;

    //     let conn = &mut db_pool.get()?;

    //     conn.transaction(|conn| {
    //         let new_plugin = NewPlugin {
    //             name: manifest.name.clone(),
    //             version: manifest.version.clone(),
    //             description: manifest.description.clone(),
    //             plugin_type: manifest.plugin_type.clone(),
    //             is_builtin,
    //             created_by_user_id,
    //         };

    //         let plugin = Plugin::insert(new_plugin, db_pool)?;

    //         if let Some(config_schema) = &manifest.config_schema {
    //             for (key, prop) in &config_schema.properties {
    //                 let config_is_required = config_schema.required.contains(key);
    //                 let config_is_secret = PluginConfig::is_secret_key(key);

    //                 diesel::insert_into(plugin_config_schema)
    //                     .values(&NewPluginConfig {
    //                         plugin_id: plugin.id,
    //                         config_key: key.clone(),
    //                         config_type: prop.property_type.clone(),
    //                         description: Some(prop.description.clone()),
    //                         is_required: config_is_required,
    //                         is_secret: config_is_secret,
    //                         default_value: prop.default.clone(),
    //                     })
    //                     .on_conflict((plugin_id, config_key))
    //                     .do_update()
    //                     .set((
    //                         config_type.eq(prop.property_type.clone()),
    //                         description.eq(&prop.description),
    //                         is_required.eq(is_required),
    //                         is_secret.eq(is_secret),
    //                         default_value.eq(&prop.default),
    //                     ))
    //                     .execute(conn)?;
    //             }
    //         }

    //         Ok(plugin.id)
    //     })
    // }

    // pub fn get(db_pool: &DbPool, key: &str) -> Result<Option<PluginConfig>, CoreError> {
    //     use crate::schema::plugin_config_schema::dsl::*;

    //     let conn = &mut db_pool.get()?;

    //     Ok(plugin_config_schema
    //         .filter(plugin_id.eq(plugin_id))
    //         .filter(config_key.eq(key))
    //         .select(PluginConfig::as_select())
    //         .first::<PluginConfig>(conn)
    //         .optional()?)
    // }

    // pub fn get_for_plugin(
    //     plugin_id_val: i32,
    //     db_pool: &DbPool,
    // ) -> Result<Vec<PluginConfig>, CoreError> {
    //     use crate::schema::plugin_config_schema::dsl::*;

    //     let conn = &mut db_pool.get()?;
    //     Ok(plugin_config_schema
    //         .filter(plugin_id.eq(plugin_id_val))
    //         .select(PluginConfig::as_select())
    //         .load::<PluginConfig>(conn)?)
    // }

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
