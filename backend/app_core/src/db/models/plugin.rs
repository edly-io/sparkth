use diesel::{pg, prelude::*};
use serde::{Deserialize, Serialize};

use crate::db::{db_pool::DbPool, error::CoreError};

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
            .on_conflict(name)
            .do_update()
            .set(UpdatePlugin {
                version: Some(plugin.version.clone()),
                description: plugin.description.clone(),
            })
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

    pub fn get_user_plugins(db_pool: DbPool, u_id: i32) -> Result<Vec<Plugin>, CoreError> {
        use crate::schema::plugins::dsl::*;
        use crate::schema::user_plugins;

        let conn = &mut db_pool.get()?;

        let user_plugins = plugins
            .left_join(
                user_plugins::table.on(user_plugins::plugin_id
                    .eq(id)
                    .and(user_plugins::user_id.eq(u_id))),
            )
            .filter(
                is_builtin
                    .eq(true)
                    .or(created_by_user_id.eq(u_id))
                    .or(user_plugins::user_id.eq(u_id)),
            )
            .distinct()
            .select(Plugin::as_select())
            .get_results(conn)?;

        Ok(user_plugins)
    }
}
