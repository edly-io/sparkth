// @generated automatically by Diesel CLI.

diesel::table! {
    plugin_settings (id) {
        id -> Int4,
        plugin_id -> Nullable<Int4>,
        settings -> Jsonb,
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

diesel::joinable!(plugin_settings -> plugins (plugin_id));

diesel::allow_tables_to_appear_in_same_query!(plugin_settings, plugins,);
