use app_core::PluginConfigService;
use axum::{
    Router,
    routing::{get, patch},
};

use crate::plugins::api::{get_plugin, list_plugins, toggle_plugin, update_plugin_config};

pub fn plugin_routes() -> Router<PluginConfigService> {
    Router::new()
        .route("/plugin/{id}", get(get_plugin))
        .route("/plugins", get(list_plugins))
        .route("/plugins/{id}/config", patch(update_plugin_config))
        .route("/plugins/{id}/toggle", patch(toggle_plugin))
}
