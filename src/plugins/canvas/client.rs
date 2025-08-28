use reqwest::{Client, Method};
use serde_json::Value;
use url::Url;

use crate::plugins::{
    errors::LMSError,
    request::{Auth, request},
    response::LMSResponse,
};

#[derive(Debug, Clone)]
pub struct CanvasClient {
    api_url: String,
    api_token: Option<String>,
    client: Client,
}

impl CanvasClient {
    pub fn new(api_url: String, api_token: String) -> Self {
        Self {
            api_url,
            api_token: Some(api_token),
            client: Client::new(),
        }
    }

    pub async fn authenticate(new_api_url: String, new_api_token: String) -> Result<(), LMSError> {
        let client = Client::new();
        let response = client
            .get(format!("{new_api_url}/users/self"))
            .bearer_auth(&new_api_token)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(LMSError::Authentication(String::from(
                "Invalid API URL or token",
            )))
        }
    }

    pub async fn request_bearer(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<LMSResponse, LMSError> {
        if self.api_token.is_none() {
            return Err(LMSError::Authentication("API Token not found".into()));
        }

        let url = Url::parse(&format!(
            "{}/{}",
            self.api_url,
            endpoint.trim_start_matches('/')
        ))?;
        let api_token = self.api_token.clone().unwrap();

        request(
            Auth::Bearer,
            &api_token,
            http_method,
            url,
            payload,
            &self.client,
        )
        .await
    }
}
