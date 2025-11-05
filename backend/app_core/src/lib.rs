pub mod db;
mod schema;
pub mod service;

pub use db::{CoreError, NewPlugin, NewUser, Plugin, User, get_db_pool, DbPool};
pub use utils::{check_user_exists, validate_email};

