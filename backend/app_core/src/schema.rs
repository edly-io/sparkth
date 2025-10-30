// @generated automatically by Diesel CLI.

diesel::table! {
    plugin_configs (id) {
        id -> Int4,
        plugin_id -> Int4,
        #[max_length = 255]
        config_key -> Varchar,
        config_value -> Nullable<Text>,
        is_secret -> Bool,
        created_at -> Timestamp,
        updated_at -> Timestamp,
    }
}

diesel::table! {
    plugins (id) {
        id -> Int4,
        #[max_length = 255]
        name -> Varchar,
        #[max_length = 50]
        version -> Varchar,
        description -> Nullable<Text>,
        enabled -> Bool,
        #[max_length = 50]
        plugin_type -> Varchar,
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

diesel::joinable!(plugin_configs -> plugins (plugin_id));

diesel::allow_tables_to_appear_in_same_query!(plugin_configs, plugins, users,);
