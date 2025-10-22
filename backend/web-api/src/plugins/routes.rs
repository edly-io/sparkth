use app_core::PluginService;
use axum::{Router, routing::get};

use crate::plugins::api::{get_plugin, get_plugins};

pub fn plugin_routes() -> Router<PluginService> {
    Router::new()
        .route("/plugin/{id}", get(get_plugin))
        .route("/plugins", get(get_plugins))
}
