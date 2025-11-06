use app_core::PluginService;
use axum::{
    Router,
    routing::{get, patch},
};

use crate::plugins::api::{get_plugin, list_plugins_for_user, toggle_plugin};

pub fn plugin_routes() -> Router<PluginService> {
    Router::new()
        .route("/plugin/{id}", get(get_plugin))
        .route("/plugins/{id}", get(list_plugins_for_user))
        // .route("/plugins/{id}/config", patch(update_plugin_config))
        .route("/plugins/{id}/toggle", patch(toggle_plugin))
}
