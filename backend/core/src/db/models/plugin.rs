use chrono::{DateTime, Utc};
use diesel::{pg, prelude::*};
use serde::{Deserialize, Serialize};

use crate::db::{db_pool::DbPool, error::CoreError};

#[derive(Debug, Deserialize, Clone, Queryable, Selectable, Serialize, Identifiable)]
#[diesel(table_name = crate::schema::plugins)]
#[diesel(primary_key(id))]
#[diesel(check_for_backend(pg::Pg))]
pub struct Plugin {
    pub id: i32,
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    pub enabled: bool,
    pub plugin_type: String,
}

#[derive(Insertable, Serialize, Deserialize)]
#[diesel(table_name = crate::schema::plugins)]
pub struct NewPlugin {
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    pub enabled: bool,
    pub plugin_type: String,
}

// #[derive(Debug, Clone, Serialize, Deserialize)]
// pub struct PluginSettings {
//     pub plugin_id: String,
//     pub settings: serde_json::Value,
//     pub updated_at: DateTime<Utc>,
// }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginWithTools {
    #[serde(flatten)]
    pub plugin: Plugin,
    pub available_tools: Vec<String>,
}

impl Plugin {
    pub fn insert(plugin: NewPlugin, db_pool: &DbPool) -> Result<Plugin, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(diesel::insert_into(plugins)
            .values(plugin)
            .returning(Plugin::as_returning())
            .get_result(conn)?)
    }

    pub fn get(plugin: i32, db_pool: &DbPool) -> Result<Plugin, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(plugins
            .find(plugin)
            .select(Plugin::as_select())
            .first(conn)?)
    }

    pub fn get_list(db_pool: &DbPool) -> Result<Vec<Plugin>, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        let results = plugins.select(Plugin::as_select()).load::<Plugin>(conn)?;

        Ok(results)
    }
}
