use async_trait::async_trait;
use reqwest::{Method, Response};
use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::plugins::{config::Config, lms_error::LmsError};

#[async_trait]
pub trait LmsClient: Send + Sync {
    fn new(config: Config) -> Self;
    async fn request<T>(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>) -> Result<T, LmsError>  
        where
        T: DeserializeOwned + Send;
    async fn handle_error_response(&self, response: Response) -> LmsError;
}