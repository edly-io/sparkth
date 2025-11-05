use chrono::{NaiveDateTime, Utc};
use diesel::{
    ExpressionMethods, Identifiable, Insertable, OptionalExtension, PgConnection, QueryDsl,
    Queryable, RunQueryDsl, Selectable,
    prelude::Associations,
    r2d2::{ConnectionManager, PooledConnection},
};
use serde::Serialize;

use crate::{CoreError, DbPool, db::models::user_plugins::UserPlugin};

#[derive(Debug, Serialize, Queryable, Selectable, Identifiable, Associations)]
#[diesel(belongs_to(UserPlugin))]
#[diesel(table_name = crate::schema::user_plugin_configs)]
pub struct UserPluginConfig {
    pub id: i32,
    pub user_plugin_id: i32,
    pub config_key: String,
    pub config_value: Option<String>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

#[derive(Debug, Insertable)]
#[diesel(table_name = crate::schema::user_plugin_configs)]
pub struct NewUserPluginConfig {
    pub user_plugin_id: i32,
    pub config_key: String,
    pub config_value: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UserPluginConfigDto {
    pub plugin_id: i32,
    pub plugin_name: String,
    pub enabled: bool,
    pub configs: Vec<UserPluginConfig>,
}

impl UserPluginConfig {
    pub fn insert(
        u_plugin_id: i32,
        key: &String,
        value: &String,
        conn: &mut PooledConnection<ConnectionManager<PgConnection>>,
    ) -> Result<usize, CoreError> {
        use crate::schema::user_plugin_configs::dsl::*;

        let res = diesel::insert_into(user_plugin_configs)
            .values(&NewUserPluginConfig {
                user_plugin_id: u_plugin_id,
                config_key: key.to_string(),
                config_value: Some(value.to_string()),
            })
            .on_conflict((user_plugin_id, config_key))
            .do_update()
            .set((
                config_value.eq(Some(value)),
                updated_at.eq(Utc::now().naive_utc()),
            ))
            .execute(conn)?;

        Ok(res)
    }

    pub fn get_user_plugin_config(
        db_pool: &DbPool,
        u_id: i32,
        plugin_name: &str,
    ) -> Result<Option<UserPluginConfigDto>, CoreError> {
        use crate::schema::plugins;
        use crate::schema::user_plugin_configs;
        use crate::schema::user_plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        let result = user_plugins
            .inner_join(plugins::table)
            .filter(user_id.eq(u_id))
            .filter(plugins::name.eq(plugin_name))
            .select((id, enabled, plugins::id, plugins::name))
            .first::<(i32, bool, i32, String)>(conn)
            .optional()?;

        let Some((user_plugin_id, is_enabled, p_id, plugin_name)) = result else {
            return Ok(None);
        };

        let configs: Vec<UserPluginConfig> = user_plugin_configs::table
            .find(user_plugin_id)
            .get_results(conn)?;

        Ok(Some(UserPluginConfigDto {
            plugin_id: p_id,
            plugin_name,
            enabled: is_enabled,
            configs,
        }))
    }
}
