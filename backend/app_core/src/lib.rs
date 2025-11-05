mod db;
mod schema;
pub mod service;
pub mod utils;
pub use db::{
    CoreError, DbPool, NewPlugin, NewUser, Plugin, PluginType, User, get_db_pool, ConfigProperty, ConfigSchema, ConfigType,
};
pub use service::PluginService;
pub use utils::{check_user_exists, validate_email};
