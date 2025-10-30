use app_core::PluginConfigService;
use axum::{
    Json, debug_handler,
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
};
use log::{error, info};
use serde::Deserialize;
use serde_json::to_value;

use crate::api_response::ApiResponse;

#[debug_handler]
pub async fn get_plugin(
    State(handler): State<PluginConfigService>,
    Path(id): Path<i32>,
) -> impl IntoResponse {
    let response = match handler.get_with_config(id) {
        Ok(plugin_with_config) => {
            let message = format!(
                "Plugin {:?} fetched successfully",
                plugin_with_config.plugin.id
            );
            info!("GET /plugin - {message}");
            let res = to_value(plugin_with_config).unwrap();
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
pub async fn list_plugins(State(handler): State<PluginConfigService>) -> impl IntoResponse {
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

#[derive(Deserialize)]
pub struct UpdateConfigRequest {
    pub config: Vec<(String, String)>,
}

pub async fn update_plugin_config(
    State(service): State<PluginConfigService>,
    Path(id): Path<i32>,
    Json(payload): Json<UpdateConfigRequest>,
) -> impl IntoResponse {
    let response = match service.update_configs(id, payload.config) {
        Ok(response) => {
            let message = format!("Updated config for plugin {id}");
            info!("PATCH /plugins/{id}/config - {message}");
            let res = to_value(response).unwrap();
            ApiResponse::new(Some(res), message, StatusCode::OK)
        }
        Err(err) => {
            let message = format!("Error updating plugin {id}: {err}");
            error!("PATCH /plugins/{id}/config - {message}");
            ApiResponse::err(None, err)
        }
    };

    Json(response)
}

#[derive(Deserialize)]
pub struct TogglePluginRequest {
    pub enabled: bool,
}

pub async fn toggle_plugin(
    State(service): State<PluginConfigService>,
    Path(id): Path<i32>,
    Json(payload): Json<TogglePluginRequest>,
) -> impl IntoResponse {
    let response = match service.set_enabled(id, payload.enabled) {
        Ok(response) => {
            let message = format!("Updated enabled for plugin {id}");
            info!("PATCH /plugins/{id}/toggle - {message}");
            let res = to_value(response).unwrap();
            ApiResponse::new(Some(res), message, StatusCode::OK)
        }
        Err(err) => {
            let message = format!("Error updating plugin {id}: {err}");
            error!("PATCH /plugins/{id}/toggle - {message}");
            ApiResponse::err(None, err)
        }
    };

    Json(response)
}
