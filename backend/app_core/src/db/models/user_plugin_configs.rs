use std::collections::HashMap;

use chrono::{NaiveDateTime, Utc};
use diesel::{
    BoolExpressionMethods, ExpressionMethods, Identifiable, Insertable, JoinOnDsl,
    NullableExpressionMethods, PgConnection, QueryDsl, Queryable, RunQueryDsl, Selectable,
    SelectableHelper,
    prelude::Associations,
    r2d2::{ConnectionManager, PooledConnection},
};
use serde::Serialize;

use crate::{CoreError, DbPool, Plugin, db::models::user_plugins::UserPlugin};

#[derive(Debug, Clone, Serialize, Queryable, Selectable, Identifiable, Associations)]
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

#[derive(Debug, Clone, Serialize)]
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

    pub fn get_user_plugin_with_configs(
        db_pool: &DbPool,
        p_id: i32,
    ) -> Result<UserPluginConfigDto, CoreError> {
        use crate::schema::plugins;
        use crate::schema::user_plugin_configs;
        use crate::schema::user_plugins::dsl::*;

        let conn = &mut db_pool.get()?;
        let result: (i32, bool, i32, String) = user_plugins
            .inner_join(plugins::table)
            .filter(plugins::id.eq(p_id))
            .select((id, enabled, plugins::id, plugins::name))
            .first(conn)?;

        let (user_plugin_id, is_enabled, p_id, plugin_name) = result;

        let configs: Vec<UserPluginConfig> = user_plugin_configs::table
            .find(user_plugin_id)
            .get_results(conn)?;

        Ok(UserPluginConfigDto {
            plugin_id: p_id,
            plugin_name,
            enabled: is_enabled,
            configs,
        })
    }

    pub fn get_user_plugins_with_configs(
        db_pool: &DbPool,
        u_id: i32,
    ) -> Result<Vec<UserPluginConfigDto>, CoreError> {
        use crate::schema::plugins;
        use crate::schema::user_plugin_configs;
        use crate::schema::user_plugins;

        let conn = &mut db_pool.get()?;

        let plugin_rows: Vec<(Plugin, Option<UserPlugin>)> = plugins::table
            .left_join(
                user_plugins::table.on(user_plugins::plugin_id
                    .eq(plugins::id)
                    .and(user_plugins::user_id.eq(u_id))),
            )
            .filter(
                plugins::is_builtin
                    .eq(true)
                    .or(plugins::created_by_user_id.eq(u_id))
                    .or(user_plugins::user_id.eq(u_id)),
            )
            .select((plugins::all_columns, user_plugins::all_columns.nullable()))
            .distinct()
            .load(conn)?;

        let user_plugin_ids: Vec<i32> = plugin_rows
            .iter()
            .filter_map(|(_, up)| up.as_ref().map(|up| up.id))
            .collect();

        let user_plugin_configs_map: HashMap<i32, Vec<UserPluginConfig>> =
            if user_plugin_ids.is_empty() {
                Default::default()
            } else {
                let configs: Vec<UserPluginConfig> = user_plugin_configs::table
                    .filter(user_plugin_configs::user_plugin_id.eq_any(&user_plugin_ids))
                    .select(UserPluginConfig::as_select())
                    .load(conn)?;

                let mut map = HashMap::new();
                for cfg in configs {
                    map.entry(cfg.user_plugin_id)
                        .or_insert_with(Vec::new)
                        .push(cfg);
                }
                map
            };

        let result: Vec<UserPluginConfigDto> = plugin_rows
            .into_iter()
            .map(|(plugin, user_plugin)| {
                let enabled = user_plugin.as_ref().map(|up| up.enabled).unwrap_or(false);
                let configs = user_plugin
                    .as_ref()
                    .and_then(|up| user_plugin_configs_map.get(&up.id).cloned())
                    .unwrap_or_default();

                UserPluginConfigDto {
                    plugin_id: plugin.id,
                    plugin_name: plugin.name,
                    enabled,
                    configs,
                }
            })
            .collect();

        Ok(result)
    }
}
