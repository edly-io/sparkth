use thiserror::Error;

pub type Result<T> = std::result::Result<T, PluginError>;

#[derive(Debug, Error)]
pub enum PluginError {
    #[error("Could not initialize: {0:?}")]
    InternalServer(#[from] app_core::CoreError),
}
