use diesel::{
    r2d2,
    result::{self, Error},
};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CoreError {
    #[error("Database Query Error  - {0:?}")]
    Database(#[source] result::Error),

    #[error("Not Found Error  - {0:?}")]
    NotFound(#[source] result::Error),

    #[error("Query Builder Error  - {0:?}")]
    QueryBuilder(#[source] result::Error),

    #[error("Pooled Connection Error - {0:?}")]
    PooledConnection(#[from] r2d2::PoolError),

    #[error("Plugin error: {0}")]
    Plugin(String),

    #[error("Authentication error: {0}")]
    AuthError(String),
}

impl From<result::Error> for CoreError {
    fn from(error: result::Error) -> Self {
        match error {
            Error::NotFound => CoreError::NotFound(error),
            Error::QueryBuilderError(_) => CoreError::QueryBuilder(error),
            _ => CoreError::Database(error),
        }
    }
}
