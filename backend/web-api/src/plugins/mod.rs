use core::service::plugin_service::PluginService;

use axum::{
    Json,
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
};
use log::{error, info};
use serde_json::to_value;

use crate::api_response::ApiResponse;

pub async fn get_plugin(
    State(handler): State<PluginService>,
    Path(id): Path<i32>,
) -> impl IntoResponse {
    let response = match handler.get(id) {
        Ok(plugin) => {
            let message = format!("Plugin {:?} fetched successfully", plugin.id);
            info!("GET /plugin - {message}");
            ApiResponse::new(Some(to_value(plugin).unwrap()), message, StatusCode::FOUND)
        }
        Err(err) => {
            let message = format!("Error retrieving plugin {id}: {err}");
            error!("GET /plugin - {message}");
            ApiResponse::err(None, err)
        }
    };
    Json(response)
}
