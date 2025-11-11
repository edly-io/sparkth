use chrono::NaiveDateTime;
use diesel::{pg, prelude::*};
use serde::{Deserialize, Serialize};

use crate::{
    PluginManifest,
    db::{db_pool::DbPool, error::CoreError},
};

#[derive(Debug, Clone, Serialize, Deserialize, diesel_derive_enum::DbEnum)]
#[ExistingTypePath = "crate::schema::sql_types::PluginTypeEnum"]
#[serde(rename_all = "lowercase")]
pub enum PluginType {
    Lms,
}

#[derive(Debug, Deserialize, Clone, Queryable, Selectable, Serialize, Identifiable)]
#[diesel(table_name = crate::schema::plugins)]
#[diesel(primary_key(id))]
#[diesel(check_for_backend(pg::Pg))]
pub struct Plugin {
    pub id: i32,
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    pub plugin_type: PluginType,
    pub is_builtin: bool,
    pub created_by_user_id: Option<i32>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

#[derive(Insertable, Serialize, Deserialize)]
#[diesel(table_name = crate::schema::plugins)]
pub struct NewPlugin {
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    pub plugin_type: PluginType,
    pub is_builtin: bool,
    pub created_by_user_id: Option<i32>,
}

#[derive(Debug, AsChangeset)]
#[diesel(table_name = crate::schema::plugins)]
pub struct UpdatePlugin {
    pub version: Option<String>,
    pub description: Option<String>,
}

impl Plugin {
    pub fn insert(plugin: NewPlugin, db_pool: &DbPool) -> Result<Plugin, CoreError> {
        use crate::schema::plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(diesel::insert_into(plugins)
            .values(&plugin)
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

    pub fn get_plugin_for_user(
        user_id: i32,
        plugin_id: i32,
        db_pool: &DbPool,
    ) -> Result<Plugin, CoreError> {
        use crate::schema::plugins::dsl::{created_by_user_id, id, is_builtin, plugins};

        let conn = &mut db_pool.get()?;
        let plugin = plugins
            .filter(
                id.eq(plugin_id)
                    .and(is_builtin.eq(true).or(created_by_user_id.eq(user_id))),
            )
            .select(Plugin::as_select())
            .first(conn)?;
        Ok(plugin)
    }

    pub fn get_list_for_user(user_id: i32, db_pool: &DbPool) -> Result<Vec<Plugin>, CoreError> {
        use crate::schema::plugins::dsl::{created_by_user_id, is_builtin, plugins};

        let conn = &mut db_pool.get()?;
        let user_plugins = plugins
            .filter(is_builtin.eq(true).or(created_by_user_id.eq(user_id)))
            .select(Plugin::as_select())
            .load(conn)?;

        Ok(user_plugins)
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
}
