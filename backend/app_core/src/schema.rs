// @generated automatically by Diesel CLI.

pub mod sql_types {
    #[derive(diesel::query_builder::QueryId, diesel::sql_types::SqlType)]
    #[diesel(postgres_type(name = "config_type_enum"))]
    pub struct ConfigTypeEnum;

    #[derive(diesel::query_builder::QueryId, diesel::sql_types::SqlType)]
    #[diesel(postgres_type(name = "plugin_type_enum"))]
    pub struct PluginTypeEnum;
}

diesel::table! {
    use diesel::sql_types::*;
    use super::sql_types::ConfigTypeEnum;

    plugin_config_schema (id) {
        id -> Int4,
        plugin_id -> Int4,
        #[max_length = 255]
        config_key -> Varchar,
        config_type -> ConfigTypeEnum,
        description -> Nullable<Text>,
        is_required -> Bool,
        is_secret -> Bool,
        default_value -> Nullable<Text>,
        created_at -> Timestamp,
    }
}

diesel::table! {
    plugin_settings (id) {
        id -> Int4,
        plugin_id -> Nullable<Int4>,
        settings -> Jsonb,
        updated_at -> Timestamp,
    }
}

diesel::table! {
    use diesel::sql_types::*;
    use super::sql_types::PluginTypeEnum;

    plugins (id) {
        id -> Int4,
        #[max_length = 255]
        name -> Varchar,
        #[max_length = 50]
        version -> Varchar,
        description -> Nullable<Text>,
        enabled -> Bool,
        plugin_type -> PluginTypeEnum,
        is_builtin -> Bool,
        created_by_user_id -> Nullable<Int4>,
        created_at -> Timestamp,
        updated_at -> Timestamp,
    }
}

diesel::table! {
    user_plugin_configs (id) {
        id -> Int4,
        user_plugin_id -> Int4,
        #[max_length = 255]
        config_key -> Varchar,
        config_value -> Nullable<Text>,
        created_at -> Timestamp,
        updated_at -> Timestamp,
    }
}

diesel::table! {
    user_plugins (id) {
        id -> Int4,
        user_id -> Int4,
        plugin_id -> Int4,
        enabled -> Bool,
        created_at -> Timestamp,
        updated_at -> Timestamp,
    }
}

diesel::table! {
    users (id) {
        id -> Int4,
        #[max_length = 255]
        username -> Varchar,
        #[max_length = 255]
        email -> Varchar,
        #[max_length = 255]
        password_hash -> Varchar,
        #[max_length = 255]
        first_name -> Nullable<Varchar>,
        #[max_length = 255]
        last_name -> Nullable<Varchar>,
        is_active -> Bool,
        is_admin -> Bool,
        created_at -> Timestamp,
        updated_at -> Timestamp,
    }
}

diesel::joinable!(plugin_config_schema -> plugins (plugin_id));
diesel::joinable!(plugin_settings -> plugins (plugin_id));
diesel::joinable!(plugins -> users (created_by_user_id));
diesel::joinable!(user_plugin_configs -> user_plugins (user_plugin_id));
diesel::joinable!(user_plugins -> plugins (plugin_id));
diesel::joinable!(user_plugins -> users (user_id));

diesel::allow_tables_to_appear_in_same_query!(
    plugin_config_schema,
    plugin_settings,
    plugins,
    user_plugin_configs,
    user_plugins,
    users,
);
