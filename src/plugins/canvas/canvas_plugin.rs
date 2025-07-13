use crate::plugins::canvas::client::CanvasClient;
use crate::plugins::canvas::config::{CanvasConfig, ConfigError};
use crate::plugins::canvas::tools::{
    AddPageToModule, CreateCourse, CreateModule, CreateModuleItem, CreatePage, DeleteModule,
    DeleteModuleItem, DeletePage, GetCourse, GetCourses, GetModule, GetModuleItem, GetPage,
    ListModuleItems, ListModules, ListPages, UpdateModule, UpdateModuleItem, UpdatePage,
};
use crate::server::tool_registry::ToolRegistry;

pub fn canvas_plugin_setup(tools: &mut ToolRegistry) -> Result<(), ConfigError> {
    let CanvasConfig { api_url, api_token } = CanvasConfig::from_env()?;
    let canvas_client = CanvasClient::new(api_url, api_token);

    tools
        .register(Box::new(CreateCourse {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(GetCourse {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(GetCourses {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(ListModules {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(GetModule {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(CreateModule {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(UpdateModule {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(DeleteModule {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(ListModuleItems {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(GetModuleItem {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(CreateModuleItem {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(UpdateModuleItem {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(DeleteModuleItem {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(ListPages {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(GetPage {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(CreatePage {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(UpdatePage {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(DeletePage {
            canvas_client: canvas_client.clone(),
        }))
        .register(Box::new(AddPageToModule {
            canvas_client: canvas_client.clone(),
        }));

    Ok(())
}
