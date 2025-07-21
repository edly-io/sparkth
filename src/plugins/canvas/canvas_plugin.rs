use crate::plugins::canvas::client::CanvasClient;
use crate::plugins::canvas::config::CanvasConfig;
use crate::server::error::ConfigError;
use crate::server::plugin::{Plugin, PluginContext};
use crate::tools::canvas_tools::{
    AddPageToModule, AddQuizToModule, CreateCourse, CreateModule, CreateModuleItem, CreatePage,
    CreateQuestion, CreateQuiz, DeleteModule, DeleteModuleItem, DeletePage, DeleteQuestion,
    DeleteQuiz, GetCourse, GetCourses, GetModule, GetModuleItem, GetPage, GetQuestion, GetQuiz,
    ListModuleItems, ListModules, ListPages, ListQuestions, ListQuizzes, UpdateModule,
    UpdateModuleItem, UpdatePage, UpdateQuestion, UpdateQuiz,
};

pub struct Canvas;

impl Plugin for Canvas {
    fn name(&self) -> &str {
        "canvas"
    }

    fn register(&self, context: &mut PluginContext) -> Result<(), ConfigError> {
        let CanvasConfig { api_url, api_token } = CanvasConfig::from_env()?;
        let canvas_client = CanvasClient::new(api_url, api_token);

        context
            .filters
            .course_filter_chain
            .add_filter(|payload, username| {
                payload.name = format!("[Canvas] {} ({})", payload.name, username);
            });

        context
            .tools
            .register(CreateCourse {
                canvas_client: canvas_client.clone(),
            })
            .register(GetCourse {
                canvas_client: canvas_client.clone(),
            })
            .register(GetCourses {
                canvas_client: canvas_client.clone(),
            })
            .register(ListModules {
                canvas_client: canvas_client.clone(),
            })
            .register(GetModule {
                canvas_client: canvas_client.clone(),
            })
            .register(CreateModule {
                canvas_client: canvas_client.clone(),
            })
            .register(UpdateModule {
                canvas_client: canvas_client.clone(),
            })
            .register(DeleteModule {
                canvas_client: canvas_client.clone(),
            })
            .register(ListModuleItems {
                canvas_client: canvas_client.clone(),
            })
            .register(GetModuleItem {
                canvas_client: canvas_client.clone(),
            })
            .register(CreateModuleItem {
                canvas_client: canvas_client.clone(),
            })
            .register(UpdateModuleItem {
                canvas_client: canvas_client.clone(),
            })
            .register(DeleteModuleItem {
                canvas_client: canvas_client.clone(),
            })
            .register(ListPages {
                canvas_client: canvas_client.clone(),
            })
            .register(GetPage {
                canvas_client: canvas_client.clone(),
            })
            .register(CreatePage {
                canvas_client: canvas_client.clone(),
            })
            .register(UpdatePage {
                canvas_client: canvas_client.clone(),
            })
            .register(DeletePage {
                canvas_client: canvas_client.clone(),
            })
            .register(AddPageToModule {
                canvas_client: canvas_client.clone(),
            })
            .register(ListQuizzes {
                canvas_client: canvas_client.clone(),
            })
            .register(GetQuiz {
                canvas_client: canvas_client.clone(),
            })
            .register(CreateQuiz {
                canvas_client: canvas_client.clone(),
            })
            .register(UpdateQuiz {
                canvas_client: canvas_client.clone(),
            })
            .register(DeleteQuiz {
                canvas_client: canvas_client.clone(),
            })
            .register(AddQuizToModule {
                canvas_client: canvas_client.clone(),
            })
            .register(ListQuestions {
                canvas_client: canvas_client.clone(),
            })
            .register(GetQuestion {
                canvas_client: canvas_client.clone(),
            })
            .register(CreateQuestion {
                canvas_client: canvas_client.clone(),
            })
            .register(UpdateQuestion {
                canvas_client: canvas_client.clone(),
            })
            .register(DeleteQuestion {
                canvas_client: canvas_client.clone(),
            });

        Ok(())
    }
}
