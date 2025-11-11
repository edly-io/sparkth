use chrono::NaiveDateTime;
use diesel::{
    AsChangeset, BoolExpressionMethods, ExpressionMethods, Identifiable, Insertable, QueryDsl,
    Queryable, RunQueryDsl, Selectable, SelectableHelper, prelude::Associations, upsert::excluded,
};
use serde::Serialize;

use crate::{CoreError, DbPool, Plugin, User, db::PluginConfig, schema::users};

#[derive(Debug, Clone, Serialize, Queryable, Selectable, Identifiable, Associations)]
#[diesel(belongs_to(User))]
#[diesel(belongs_to(Plugin))]
#[diesel(table_name = crate::schema::user_plugin_configs)]
pub struct UserPluginConfig {
    pub id: i32,
    pub user_id: i32,
    pub plugin_id: i32,
    pub config_key: String,
    pub enabled: bool,
    pub config_value: Option<String>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

#[derive(Insertable, AsChangeset)]
#[diesel(table_name = crate::schema::user_plugin_configs)]
pub struct UpsertUserPluginConfig {
    pub user_id: i32,
    pub plugin_id: i32,
    pub config_key: String,
    pub config_value: String,
}

#[derive(Insertable)]
#[diesel(table_name = crate::schema::user_plugin_configs)]
struct NewUserPluginConfig {
    user_id: i32,
    plugin_id: i32,
    config_key: String,
    config_value: Option<String>,
    enabled: bool,
}

impl UserPluginConfig {
    pub fn upsert(
        records: Vec<UpsertUserPluginConfig>,
        db_pool: &DbPool,
    ) -> Result<usize, CoreError> {
        use crate::schema::user_plugin_configs::dsl::{
            config_key, config_value, plugin_id, user_plugin_configs,
        };

        let conn = &mut db_pool.get()?;
        let result = diesel::insert_into(user_plugin_configs)
            .values(&records)
            .on_conflict((plugin_id, config_key))
            .do_update()
            .set(config_value.eq(excluded(config_value)))
            .execute(conn)?;

        Ok(result)
    }

    pub fn install_builtin_for_all_users(p_id: i32, db_pool: &DbPool) -> Result<(), CoreError> {
        use crate::schema::user_plugin_configs::dsl::{
            config_key, plugin_id, user_id, user_plugin_configs,
        };
        let conn = &mut db_pool.get()?;

        let user_ids: Vec<i32> = users::table.select(users::id).load(conn)?;
        if user_ids.is_empty() {
            return Ok(());
        }

        let configs = PluginConfig::get_plugin_config_schema(p_id, db_pool)?;
        if configs.is_empty() {
            return Ok(());
        }

        let new_rows: Vec<NewUserPluginConfig> = user_ids
            .iter()
            .flat_map(|u_id| {
                configs.iter().map(move |config| NewUserPluginConfig {
                    user_id: *u_id,
                    plugin_id: p_id,
                    config_key: config.config_key.clone(),
                    config_value: config.default_value.clone(),
                    enabled: false,
                })
            })
            .collect();

        diesel::insert_into(user_plugin_configs)
            .values(&new_rows)
            .on_conflict((user_id, plugin_id, config_key))
            .do_nothing()
            .execute(conn)?;

        Ok(())
    }

    pub fn get_user_configs_for_plugin(
        u_id: i32,
        p_id: i32,
        db_pool: &DbPool,
    ) -> Result<Vec<UserPluginConfig>, CoreError> {
        use crate::schema::user_plugin_configs::dsl::{plugin_id, user_id, user_plugin_configs};

        let conn = &mut db_pool.get()?;
        Ok(user_plugin_configs
            .filter(user_id.eq(u_id).and(plugin_id.eq(p_id)))
            .select(UserPluginConfig::as_select())
            .load(conn)?)
    }

    pub fn get_user_configs_for_plugins_list(
        u_id: i32,
        plugin_ids: Vec<i32>,
        db_pool: &DbPool,
    ) -> Result<Vec<UserPluginConfig>, CoreError> {
        use crate::schema::user_plugin_configs::dsl::{plugin_id, user_id, user_plugin_configs};

        let conn = &mut db_pool.get()?;

        let user_configs: Vec<UserPluginConfig> = user_plugin_configs
            .filter(user_id.eq(u_id).and(plugin_id.eq_any(&plugin_ids)))
            .select(UserPluginConfig::as_select())
            .load(conn)?;
        Ok(user_configs)
    }

    pub fn update_user_plugin_enabled(
        db_pool: &DbPool,
        u_id: i32,
        p_id: i32,
        is_enabled: bool,
    ) -> Result<usize, CoreError> {
        use crate::schema::user_plugin_configs::dsl::{
            enabled, plugin_id, user_id, user_plugin_configs,
        };

        let conn = &mut db_pool.get()?;

        let updated =
            diesel::update(user_plugin_configs.filter(user_id.eq(u_id).and(plugin_id.eq(p_id))))
                .set(enabled.eq(is_enabled))
                .execute(conn)?;

        Ok(updated)
    }
}
