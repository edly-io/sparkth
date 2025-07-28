use crate::{
    prompts,
    server::{
        error::ConfigError,
        plugin::{Plugin, PluginContext},
    },
};
use chrono::{DateTime, Utc};
use rmcp::{
    Error, ServerHandler,
    handler::server::tool::{Parameters, ToolRouter},
    model::{
        CallToolResult, Content, ErrorCode, Implementation, ProtocolVersion, ServerCapabilities,
        ServerInfo,
    },
    schemars::{self, JsonSchema},
    tool, tool_handler, tool_router,
};
use serde::Deserialize;
use serde_json::Value;
use std::sync::{Arc, Mutex};

#[derive(JsonSchema, Deserialize)]
pub struct CourseGenerationPromptRequest {
    #[schemars(description = "the duration of the course")]
    pub course_duration: String,
    #[schemars(description = "the name of the course")]
    pub course_name: String,
    #[schemars(description = "a brief description of the course")]
    pub course_description: String,
    #[schemars(description = "the start date of the course")]
    pub start_at: DateTime<Utc>,
    #[schemars(description = "the end date of the course")]
    pub end_at: DateTime<Utc>,
}

#[derive(JsonSchema, Deserialize)]
pub struct DispatchRequest {
    #[schemars(description = "the name of the tool to be dispatched")]
    tool_name: String,
    #[schemars(description = "the args to be passed to the tool")]
    args: Option<Value>,
}

#[derive(Clone)]
pub struct SparkthMCPServer {
    plugins: Arc<Mutex<Vec<Box<dyn Plugin>>>>,
    plugin_context: Arc<Mutex<PluginContext>>,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl SparkthMCPServer {
    pub fn new(plugin_context: PluginContext) -> Self {
        Self {
            plugins: Arc::new(Mutex::new(Vec::new())),
            plugin_context: Arc::new(Mutex::new(plugin_context)),
            tool_router: Self::tool_router(),
        }
    }

    pub fn load<P: Plugin + 'static>(&mut self, plugin: P) -> Result<(), ConfigError> {
        let mut context = self.plugin_context.lock().unwrap();
        plugin.register(&mut context)?;

        let mut plugins = self.plugins.lock().unwrap();
        plugins.push(Box::new(plugin));

        Ok(())
    }

    #[tool(description = "call a tool by name. The tool schema is defined below:
        tools: [{
                name: get_courses
                description: Get all the courses from the Canvas account,
            },
            {
                name: get_course
                description: Get a single course from the canvas account,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the course,
                        }
                    }
                    required: [course_id],
                }
            },
            {
                name: create_course
                description: Create a single course on the Canvas account,
                input_schema: {
                    type: object,
                    properties: {
                        account_id: {
                            type: string,
                            description: The unique identifier for the Canvas account,
                        },
                        name: {
                            type: string,
                            description: The name of the course,
                        },
                        is_public: {
                            type: boolean,
                            description: Whether the course is public to both authenticated and unauthenticated users or not.
                        },
                        course_format: {
                            type: string,
                            description: The format of the course, should be `online`, `on_campus` or `blended`.
                        },
                        course_code: {
                            type: string,
                            description: The code for the course,
                        },
                        sis_course_id: {
                            type: string,
                            description: The SIS course id.,
                        }

                    }
                    required: [account_id, name, is_public],
                }
            },
            {
                name: List_modules
                description: Fetches all modules for a course and lists them in a structured format,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        }
                    }
                    required: [course_id],
                }
            },
            {
                name: get_module
                description: Get a single module of the Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the course module,
                        },
                    }
                    required: [course_id, module_id],
                }
            },
            {
                name: create_module,
                description: Create a new module in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        name: {
                            type: string,
                            description: The name of the module,
                        },
                        position: {
                            type: integer,
                            description: The position of this module in the course (optional, default is auto-assigned),
                        },
                        unlock_at: {
                            type: string,
                            description: Date/time (ISO 8601) when the module should unlock,
                        },
                        require_sequential_progress: {
                            type: boolean,
                            description: Whether students must progress through the module sequentially,
                        },
                        prerequisite_module_ids: {
                            type: array,
                            items: {
                                type: string,
                            },
                            description: List of module IDs that must be completed before this one unlocks,
                        },
                        publish_final_grade: {
                            type: boolean,
                            description: Whether the module contributes to the final grade calculation,
                        },
                    },
                    required: [course_id, name],
                }
            },
            {
                name: update_module,
                description: Update an existing module in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the module to update,
                        },
                        name: {
                            type: string,
                            description: The new name for the module (optional),
                        },
                        position: {
                            type: integer,
                            description: The new position of the module in the course (optional),
                        },
                        unlock_at: {
                            type: string,
                            description: New unlock date/time in ISO 8601 format (optional),
                        },
                        require_sequential_progress: {
                            type: boolean,
                            description: Whether students must progress sequentially (optional),
                        },
                        prerequisite_module_ids: {
                            type: array,
                            items: {
                                type: string,
                            },
                            description: Updated list of prerequisite module IDs (optional),
                        },
                        publish_final_grade: {
                            type: boolean,
                            description: Whether the module contributes to the final grade calculation (optional),
                        },
                    },
                    required: [course_id, module_id],
                }
            },
            {
                name: delete_module,
                description: Delete a module from a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the module to delete,
                        },
                    },
                    required: [course_id, module_id],
                }
            },
            {
                name: list_module_items,
                description: List all items in a specific module of a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the module to list items for,
                        },
                    },
                    required: [course_id, module_id],
                }
            },
            {
                name: get_module_item,
                description: Get details of a specific item in a module of a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the module containing the item,
                        },
                        item_id: {
                            type: string,
                            description: The unique identifier of the item to retrieve details for,
                        },
                    },
                    required: [course_id, module_id, item_id],
                }
            },
            {
                name: create_module_item,
                description: Create a new item in a specific module of a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        module_id: {
                            type: string,
                            description: The unique identifier of the module this item belongs to,
                        },
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        title: {
                            type: string,
                            description: The title of the module item,
                        },
                        item_type: {
                            type: string,
                            description: The type of the module item (e.g., Page, Assignment, Quiz),
                        },
                        content_id: {
                            type: string,
                            description: The ID of the associated content (optional),
                        },
                        position: {
                            type: integer,
                            description: The position of the item within the module (optional),
                        },
                        indent: {
                            type: integer,
                            description: The indentation level of the item in the module UI (optional),
                        },
                        page_url: {
                            type: string,
                            description: The URL of an internal Canvas page (used when item_type is Page) (optional),
                        },
                        external_url: {
                            type: string,
                            description: A valid external URL for ExternalUrl type items (optional),
                        },
                        new_tab: {
                            type: boolean,
                            description: Whether to open the external URL in a new tab (optional),
                        },
                        completion_requirement: {
                            type: object,
                            description: Completion requirement settings for the module item (optional),
                        },
                    },
                    required: [module_id, course_id, title, item_type],
                }
            },
            {
                name: update_module_item,
                description: Update an existing item in a specific module of a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        module_id: {
                            type: string,
                            description: The unique identifier of the module containing the item,
                        },
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        item_id: {
                            type: string,
                            description: The unique identifier of the module item to update,
                        },
                        title: {
                            type: string,
                            description: The new title of the module item (optional),
                        },
                        position: {
                            type: integer,
                            description: The new position of the item within the module (optional),
                        },
                        indent: {
                            type: integer,
                            description: The updated indentation level in the module UI (optional),
                        },
                        external_url: {
                            type: string,
                            description: A new external URL to link to (for ExternalUrl item types) (optional),
                        },
                        new_tab: {
                            type: boolean,
                            description: Whether the external URL should open in a new tab (optional),
                        },
                        completion_requirement: {
                            type: object,
                            description: Updated completion requirement settings for the module item (optional),
                        },
                    },
                    required: [module_id, course_id, item_id],
                }
            },
            {
                name: delete_module_item,
                description: Delete an item from a specific module of a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        module_id: {
                            type: string,
                            description: The unique identifier of the module containing the item,
                        },
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        item_id: {
                            type: string,
                            description: The unique identifier of the module item,
                        },
                    },
                    required: [module_id, course_id, item_id],
                }
            },
            {
                name: list_pages,
                description: List all pages in a Canvas course, optionally filtered by search term,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        search_term: {
                            type: string,
                            description: Optional search term to filter pages by title or content,
                        },
                    },
                    required: [course_id],
                }
            },
            {
                name: get_page,
                description: Get details of a specific page in a Canvas course by URL,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        page_url: {
                            type: string,
                            description: The URL of the page to retrieve details for,
                        },
                    },
                    required: [course_id, page_url],
                }
            },
            {
                name: create_page,
                description: Create a new page in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        title: {
                            type: string,
                            description: The title of the new page,
                        },
                        body: {
                            type: string,
                            description: The HTML content of the page body,
                        },
                        editing_roles: {
                            type: string,
                            description: Roles allowed to edit the page (e.g., teachers, admins) (optional),
                        },
                        published: {
                            type: boolean,
                            description: Whether the page should be published upon creation (optional),
                        },
                        front_page: {
                            type: boolean,
                            description: Whether the page should be set as the front page of the course (optional),
                        },
                    },
                    required: [course_id, title, body],
                }
            },
            {
                name: update_page,
                description: Update an existing page in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        page_url: {
                            type: string,
                            description: The URL of the page to update,
                        },
                        title: {
                            type: string,
                            description: The new title of the page (optional),
                        },
                        body: {
                            type: string,
                            description: The updated HTML content of the page body (optional),
                        },
                        editing_roles: {
                            type: string,
                            description: Updated roles allowed to edit the page (optional),
                        },
                        published: {
                            type: boolean,
                            description: Whether to publish the page after updating (optional),
                        },
                        front_page: {
                            type: boolean,
                            description: Whether to set this page as the front page of the course (optional),
                        },
                    },
                    required: [course_id, page_url],
                }
            },
            {
                name: delete_page,
                description: Delete a specific page in a Canvas course by URL,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        page_url: {
                            type: string,
                            description: The URL of the page to delete,
                        },
                    },
                    required: [course_id, page_url],
                }
            },
            {
                name: add_page_to_module,
                description: Add an existing page as an item in a module within a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the module where the page will be added,
                        },
                        page_url: {
                            type: string,
                            description: The URL slug of the page to add to the module,
                        },
                        title: {
                            type: string,
                            description: Custom title for the page item (optional),
                        },
                        position: {
                            type: integer,
                            description: The position of the page item within the module (optional),
                        },
                        indent: {
                            type: integer,
                            description: The indentation level of the page item in the module UI (optional),
                        },
                        new_tab: {
                            type: boolean,
                            description: Whether the page should open in a new tab when accessed (optional),
                        },
                    },
                    required: [course_id, module_id, page_url],
                }
            },
            {
                name: list_quizzes
                description: Fetch quizzes of a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the course whose quizzes are to be listed,
                        }
                    }
                    required: [course_id],
                }
            }, 
            {
                name: get_quiz,
                description: Retrieve a specific quiz from a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz to retrieve,
                        },
                    },
                    required: [course_id, quiz_id],
                }
            },
            {
                name: create_quiz,
                description: Create a new quiz in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        title: {
                            type: string,
                            description: The title of the quiz,
                        },
                        description: {
                            type: string,
                            description: The description or instructions for the quiz,
                        },
                        quiz_type: {
                            type: string,
                            description: The type of the quiz (e.g., assignment, graded_survey, practice_quiz),
                        },
                        time_limit: {
                            type: integer,
                            description: Time limit to complete the quiz in minutes (optional),
                        },
                        published: {
                            type: boolean,
                            description: Whether the quiz should be published immediately (optional),
                        },
                    },
                    required: [course_id, title, description, quiz_type],
                }
            },
            {
                name: update_quiz,
                description: Update an existing quiz in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz to update,
                        },
                        title: {
                            type: string,
                            description: The new title of the quiz (optional),
                        },
                        description: {
                            type: string,
                            description: Updated description or instructions for the quiz (optional),
                        },
                        quiz_type: {
                            type: string,
                            description: Updated type of the quiz (optional),
                        },
                        notify_of_update: {
                            type: boolean,
                            description: Whether to notify students of the update (default is false),
                        },
                        time_limit: {
                            type: integer,
                            description: New time limit in minutes (optional),
                        },
                        published: {
                            type: boolean,
                            description: Whether to publish the updated quiz immediately (optional),
                        },
                    },
                    required: [course_id, quiz_id],
                }
            },
            {
                name: update_quiz,
                description: Update the settings or content of an existing quiz in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz to update,
                        },
                        title: {
                            type: string,
                            description: The new title of the quiz (optional),
                        },
                        description: {
                            type: string,
                            description: The new description or instructions for the quiz (optional),
                        },
                        quiz_type: {
                            type: string,
                            description: The updated type of the quiz (optional),
                        },
                        notify_of_update: {
                            type: boolean,
                            description: Whether to notify users about the quiz update,
                        },
                        time_limit: {
                            type: integer,
                            description: Updated time limit in minutes for the quiz (optional),
                        },
                        published: {
                            type: boolean,
                            description: Whether the quiz should be marked as published (optional),
                        },
                    },
                    required: [course_id, quiz_id, notify_of_update],
                }
            },
            {
                name: delete_quiz,
                description: Delete a specific quiz from a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz to delete,
                        },
                    },
                    required: [course_id, quiz_id],
                }
            },
            {
                name: add_quiz_to_module,
                description: Add an existing quiz as an item in a module within a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        module_id: {
                            type: string,
                            description: The unique identifier of the module where the quiz will be added,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz to add to the module,
                        },
                        title: {
                            type: string,
                            description: Custom title for the quiz item (optional),
                        },
                        position: {
                            type: integer,
                            description: The position of the quiz item within the module (optional),
                        },
                        indent: {
                            type: integer,
                            description: The indentation level of the quiz item in the module UI (optional),
                        },
                        new_tab: {
                            type: boolean,
                            description: Whether the quiz should open in a new tab when accessed (optional),
                        },
                    },
                    required: [course_id, module_id, quiz_id],
                }
            },
            {
                name: list_questions,
                description: Retrieve all the questions from a quiz in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz containing the questions,
                        }
                    },
                    required: [course_id, quiz_id],
                }
            },
            {
                name: get_question,
                description: Retrieve a specific question from a quiz in a Canvas course,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz containing the question,
                        },
                        question_id: {
                            type: string,
                            description: The unique identifier of the quiz question,
                        },
                    },
                    required: [course_id, quiz_id, question_id],
                }
            },
            {
                name: create_question,
                description: Create a new question in a Canvas quiz,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz to add the question to,
                        },
                        name: {
                            type: string,
                            description: The name of the quiz question,
                        },
                        text: {
                            type: string,
                            description: The text content of the quiz question,
                        },
                        question_type: {
                            type: string,
                            description: The type of question (e.g., multiple_choice_question, true_false_question) (optional),
                        },
                        points_possible: {
                            type: number,
                            description: The number of points assigned to this question (optional),
                        },
                        answers: {
                            type: array,
                            items: {
                                type: object,
                                properties: {
                                    answer_text: {
                                        type: string,
                                        description: The text content of the answer choice,
                                    },
                                    answer_weight: {
                                        type: integer,
                                        description: The score or weight assigned to this answer,
                                    },
                                    answer_comments: {
                                        type: string,
                                        description: Optional feedback or comment shown with this answer,
                                    },
                                },
                                required: [answer_text, answer_weight],
                            },
                            description: List of possible answers for the question,
                        },
                    },
                    required: [course_id, quiz_id, name, text, answers],
                }
            },
            {
                name: update_quiz_question,
                description: Update the details of a specific question in a Canvas quiz,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz containing the question,
                        },
                        question_id: {
                            type: string,
                            description: The unique identifier of the question to update,
                        },
                        name: {
                            type: string,
                            description: The new name/title of the quiz question (optional),
                        },
                        text: {
                            type: string,
                            description: The updated text/content of the quiz question (optional),
                        },
                        question_type: {
                            type: string,
                            description: The updated type of the question (e.g., multiple_choice_question) (optional),
                        },
                        points_possible: {
                            type: number,
                            description: The updated point value for the question (optional),
                        },
                        answers: {
                            type: array,
                            items: {
                                type: object,
                                properties: {
                                    answer_text: {
                                        type: string,
                                        description: The text content of the answer choice,
                                    },
                                    answer_weight: {
                                        type: integer,
                                        description: The score or weight assigned to this answer,
                                    },
                                    answer_comments: {
                                        type: string,
                                        description: Optional feedback or comment shown with this answer,
                                    },
                                },
                                required: [answer_text, answer_weight],
                            },
                            description: A new or updated list of answer choices (optional),
                        },
                    },
                    required: [course_id, quiz_id, question_id],
                }
            },
            {
                name: delete_question,
                description: Delete a specific question from a Canvas quiz,
                input_schema: {
                    type: object,
                    properties: {
                        course_id: {
                            type: string,
                            description: The unique identifier for the Canvas course,
                        },
                        quiz_id: {
                            type: string,
                            description: The unique identifier of the quiz containing the question,
                        },
                        question_id: {
                            type: string,
                            description: The unique identifier of the question to delete,
                        },
                    },
                    required: [course_id, quiz_id, question_id],
                }
            }]

            If any of the required properties is missing, ask from the user to provide them istead of assuming values. 
            Ask for normal human-readable values, not technical terms. For example, if the course name is required, ask the user to provide the name of the course. 
            The IDs can mostly be found in the chat context, so you can use them directly. If they're not present, ask the user to provide them.
")]
    pub async fn dispatch_tool(
        &self,
        Parameters(DispatchRequest { tool_name, args }): Parameters<DispatchRequest>,
    ) -> Result<CallToolResult, Error> {
        let tools = self.plugin_context.lock().unwrap().tools.clone();
        match tools.call(&tool_name, args).await {
            Some(result) => match result {
                Ok(tool_result) => Ok(tool_result),
                Err(e) => {
                    let msg = format!("Error while calling tool '{}': {}", tool_name, e);
                    Err(Error::new(ErrorCode::INTERNAL_ERROR, msg, None))
                }
            },
            None => {
                let msg = format!("Tool '{}' not found.", tool_name);
                Err(Error::new(ErrorCode::METHOD_NOT_FOUND, msg, None))
            }
        }
    }

    #[tool(
        description = "Generates a prompt for creating a course based on the parameters required. 
        If any of the parameters is not provided, always ask for it instead of assuming values.

        When generating the actual course content, follow the checklist:
- ILO & Curriculum Alignment
Are there 3-5 SMART learning outcomes?
Does each content block map to at least one ILO?
Are assessments aligned to intended performance outcomes (not just recall)?

- Cognitive Load
Are lessons broken into manageable chunks (max 5-7 min read time)?
Are complex concepts split and scaffolded across lessons? 

- Assessment Quality
Are formative assessments present throughout the course (knowledge checks)?
Do summative assessments target higher-order thinking (where applicable)?

- Spaced Repetition / Interleaving
Are key concepts revisited in later modules?
Are practice questions interleaved with related topics?

Cross-question the user to get the required and correct information. In case of any confusion, ask for clarification.   
        "
    )]
    pub fn get_course_generation_prompt(
        &self,
        Parameters(CourseGenerationPromptRequest {
            course_name,
            course_duration,
            course_description,
            start_at,
            end_at,
        }): Parameters<CourseGenerationPromptRequest>,
    ) -> Result<CallToolResult, Error> {
        let prompt = prompts::get_course_generation_prompt(
            &course_name,
            &course_duration,
            &course_description,
            start_at,
            end_at,
        );
        Ok(CallToolResult::success(vec![Content::text(prompt)]))
    }

    #[tool(description = "list all the available tools.")]
    pub fn list_tools(&self) -> Result<CallToolResult, Error> {
        let tools = self
            .plugin_context
            .lock()
            .unwrap()
            .tools
            .list_tools()
            .join("\n");
        Ok(CallToolResult::success(vec![Content::text(tools)]))
    }
}

#[tool_handler]
impl ServerHandler for SparkthMCPServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation::from_build_env(),
            instructions: Some(format!(
                "This server provides the following tools:\n{:?}.",
                self.list_tools()
            )),
        }
    }
}
