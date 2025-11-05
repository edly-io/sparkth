use chrono::{NaiveDateTime, Utc};
use diesel::{
    Connection, ExpressionMethods, QueryDsl, RunQueryDsl, Selectable, SelectableHelper,
    prelude::{AsChangeset, Associations, Identifiable, Insertable, Queryable},
};

use crate::{
    CoreError, DbPool, Plugin, User,
    db::{PluginConfig, models::user_plugin_configs::UserPluginConfig},
};

#[derive(Debug, Queryable, Selectable, Identifiable, Associations)]
#[diesel(belongs_to(Plugin))]
#[diesel(belongs_to(User))]
#[diesel(table_name = crate::schema::user_plugins)]
pub struct UserPlugin {
    pub id: i32,
    pub user_id: i32,
    pub plugin_id: i32,
    pub enabled: bool,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

#[derive(Debug, Insertable)]
#[diesel(table_name = crate::schema::user_plugins)]
pub struct NewUserPlugin {
    pub user_id: i32,
    pub plugin_id: i32,
    pub enabled: bool,
}

#[derive(Debug, AsChangeset)]
#[diesel(table_name = crate::schema::user_plugins)]
pub struct UpdateUserPlugin {
    pub enabled: Option<bool>,
    pub updated_at: NaiveDateTime,
}

impl UserPlugin {
    pub fn install_plugin_for_user(
        db_pool: &DbPool,
        u_id: i32,
        p_id: i32,
        config_values: Vec<(String, String)>,
    ) -> Result<i32, CoreError> {
        use crate::schema::user_plugins::dsl::{plugin_id, updated_at, user_id, user_plugins};

        let mut conn = db_pool.get()?;

        conn.transaction(|conn| {
            let user_plugin = diesel::insert_into(user_plugins)
                .values(&NewUserPlugin {
                    user_id: u_id,
                    plugin_id: p_id,
                    enabled: false,
                })
                .on_conflict((user_id, plugin_id))
                .do_update()
                .set(updated_at.eq(Utc::now().naive_utc()))
                .returning(UserPlugin::as_returning())
                .get_result(conn)?;

            let schema = PluginConfig::get_plugin_config_schema(p_id, conn)?;

            for (config_key, is_required, default_value) in schema {
                let value = config_values
                    .iter()
                    .find(|config| config.0 == config_key)
                    .map(|(_, val)| val.clone())
                    .or(default_value);

                if is_required && value.is_none() {
                    return Err(CoreError::Database(
                        diesel::result::Error::RollbackTransaction,
                    ));
                }

                if let Some(value) = value {
                    UserPluginConfig::insert(user_plugin.id, &config_key, &value, conn)?;
                }
            }

            Ok(user_plugin.id)
        })
    }

    pub fn set_user_plugin_enabled(
        db_pool: &DbPool,
        u_id: i32,
        p_id: i32,
        is_enabled: bool,
    ) -> Result<(), CoreError> {
        use crate::schema::user_plugins::dsl::*;

        let mut conn = db_pool.get()?;
        diesel::update(
            user_plugins
                .filter(user_id.eq(u_id))
                .filter(plugin_id.eq(p_id)),
        )
        .set(UpdateUserPlugin {
            enabled: Some(is_enabled),
            updated_at: Utc::now().naive_utc(),
        })
        .execute(&mut conn)?;

        Ok(())
    }
}
