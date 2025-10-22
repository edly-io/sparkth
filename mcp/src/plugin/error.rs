use thiserror::Error;

pub type Result<T> = std::result::Result<T, PluginError>;

#[derive(Debug, Error)]
pub enum PluginError {
    // #[error("Not found: {0:?}")]
    // NotFound(String),
    // #[error("Not implemented: {0:?}")]
    // NotImplemented(String),
    // #[error("Invalid input: {0:?}")]
    // InvalidInput(String),
    // #[error("Execution Error: {0:?}")]
    // Execution(String),
    // #[error("Config error: {0:?}")]
    // Config(String),
    // #[error("Could not activate: {0:?}")]
    // Activation(String),
    // #[error("Could not initialize: {0:?}")]
    // Initialization(String),
    #[error("Could not initialize: {0:?}")]
    InternalServer(#[from] app_core::CoreError),
}
