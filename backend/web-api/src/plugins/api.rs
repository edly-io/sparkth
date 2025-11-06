use app_core::service::PluginService;
use axum::{
    Json, debug_handler,
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
};
use log::{error, info};
use serde_json::to_value;

use crate::api_response::ApiResponse;

#[debug_handler]
pub async fn get_plugin(
    State(handler): State<PluginService>,
    Path(id): Path<i32>,
) -> impl IntoResponse {
    let response = match handler.get(id) {
        Ok(plugin) => {
            let message = format!("Plugin {:?} fetched successfully", plugin.id);
            info!("GET /plugin - {message}");
            let res = to_value(plugin).unwrap();
            ApiResponse::new(Some(res), message, StatusCode::FOUND)
        }
        Err(err) => {
            let message = format!("Error retrieving plugin {id}: {err}");
            error!("GET /plugin - {message}");
            ApiResponse::err(None, err)
        }
    };
    Json(response)
}

#[debug_handler]
pub async fn get_plugins(State(handler): State<PluginService>) -> impl IntoResponse {
    let response = match handler.get_list() {
        Ok(plugins) => {
            let message = format!("Fetched {} plugins", plugins.len());
            info!("GET /plugins - {message}");
            let res = to_value(plugins).unwrap();
            ApiResponse::new(Some(res), message, StatusCode::FOUND)
        }
        Err(err) => {
            let message = format!("Error retrieving plugins: {err}");
            error!("GET /plugins - {message}");
            ApiResponse::err(None, err)
        }
    };
    Json(response)
}
