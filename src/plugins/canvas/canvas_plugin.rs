use crate::plugins::canvas::client::CanvasClient;
use crate::plugins::canvas::config::CanvasConfig;
use crate::register_tools;
use crate::server::error::ConfigError;
use crate::server::plugin::{Plugin, PluginContext};
use crate::tools::canvas_tools::{CreateCourse, CreateModule, CreateModuleItem, CreatePage, CreateQuestion, CreateQuiz, CreateUser, DeleteModule, DeleteModuleItem, DeletePage, DeleteQuestion, DeleteQuiz, EnrollUser, GetCourse, GetCourses, GetModule, GetModuleItem, GetPage, GetQuestion, GetQuiz, ListModuleItems, ListModules, ListPages, ListQuestions, ListQuizzes, ListUsers, UpdateModule, UpdateModuleItem, UpdatePage, UpdateQuestion, UpdateQuiz};

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
                payload.course.name = format!("[Canvas] {} ({})", payload.course.name, username);
            });

        register_tools!(
            context,
            canvas_client,
            [
                CreateCourse,
                GetCourse,
                GetCourses,
                ListModules,
                GetModule,
                CreateModule,
                UpdateModule,
                DeleteModule,
                ListModuleItems,
                GetModuleItem,
                CreateModuleItem,
                UpdateModuleItem,
                DeleteModuleItem,
                ListPages,
                GetPage,
                CreatePage,
                UpdatePage,
                DeletePage,
                // AddPageToModule,
                ListQuizzes,
                GetQuiz,
                CreateQuiz,
                UpdateQuiz,
                DeleteQuiz,
                // AddQuizToModule,
                ListQuestions,
                GetQuestion,
                CreateQuestion,
                UpdateQuestion,
                DeleteQuestion,
                ListUsers,
                CreateUser,
                EnrollUser
            ]
        );

        Ok(())
    }
}
