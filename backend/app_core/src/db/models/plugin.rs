use diesel::{pg, prelude::*};
use serde::{Deserialize, Serialize};

use crate::{
    db::{db_pool::DbPool, error::CoreError},
    service::ConfigSchema,
};

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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    pub id: String,
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    pub authors: Vec<String>,
    #[serde(rename = "type")]
    pub plugin_type: PluginType,
    pub config_schema: Option<ConfigSchema>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PluginType {
    Lms,
    Storage,
    AI,
    Analytics,
    Custom,
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

    pub fn get_by_name(plugin: String, db_pool: &DbPool) -> Result<Option<Plugin>, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(plugins
            .filter(name.eq(plugin))
            .select(Plugin::as_select())
            .first::<Plugin>(conn)
            .optional()?)
    }

    pub fn get_list(db_pool: &DbPool) -> Result<Vec<Plugin>, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        let results = plugins.select(Plugin::as_select()).load::<Plugin>(conn)?;

        Ok(results)
    }

    pub fn update_version(
        plugin_id: i32,
        manifest: &PluginManifest,
        db_pool: &DbPool,
    ) -> Result<Plugin, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(diesel::update(plugins.find(plugin_id))
            .set((
                version.eq(&manifest.version),
                description.eq(&manifest.description),
            ))
            .returning(Plugin::as_returning())
            .get_result(conn)?)
    }

    pub fn set_enabled(
        plugin_id: i32,
        is_enabled: bool,
        db_pool: &DbPool,
    ) -> Result<Plugin, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(diesel::update(plugins.find(plugin_id))
            .set(enabled.eq(is_enabled))
            .returning(Plugin::as_returning())
            .get_result(conn)?)
    }
}
