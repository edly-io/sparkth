use std::sync::{Arc, Mutex};

use reqwest::{Client, Method, Response};
use serde_json::{Value, from_str};

use crate::server::{error::CanvasError, types::CanvasResponse};

#[derive(Debug, Clone)]
pub struct CanvasClient {
    api_url: Arc<Mutex<String>>,
    api_token: Arc<Mutex<Option<String>>>,
    client: Client,
}

impl CanvasClient {
    pub fn default() -> Self {
        Self {
            api_url: Arc::new(Mutex::new(String::new())),
            api_token: Arc::new(Mutex::new(None)),
            client: Client::new(),
        }
    }

    pub async fn authenticate(
        &self,
        new_api_url: String,
        new_api_token: String,
    ) -> Result<(), CanvasError> {
        let response = self
            .client
            .get(format!("{new_api_url}/users/self"))
            .bearer_auth(&new_api_token)
            .send()
            .await?;

        if response.status().is_success() {
            let mut api_url = self.api_url.lock().unwrap();
            *api_url = new_api_url;

            let mut api_token = self.api_token.lock().unwrap();
            *api_token = Some(new_api_token);

            Ok(())
        } else {
            Err(CanvasError::Authentication(String::from(
                "Invalid API URL or token",
            )))
        }
    }

    pub async fn request(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<CanvasResponse, CanvasError> {
        let url = {
            let api_url = self.api_url.lock().unwrap();
            format!("{}/{}", *api_url, endpoint.trim_start_matches('/'))
        };

        let api_token = {
            let api_token = self.api_token.lock().unwrap();
            api_token
                .clone()
                .ok_or(CanvasError::Authentication("API Token not found".into()))?
        };

        let mut request = self
            .client
            .request(http_method, &url)
            .header("Authorization", format!("Bearer {api_token}"));

        if let Some(payload) = payload {
            request = request.json(&payload);
        }

        let response = request.send().await?;

        if !response.status().is_success() {
            return Err(self.handle_error_response(response).await);
        }

        let response_text = response.text().await?;

        if response_text.is_empty() {
            return Ok(CanvasResponse::Single(
                Value::Object(serde_json::Map::new()),
            ));
        }

        let json_value: Value = from_str(&response_text)?;

        match json_value {
            Value::Array(arr) => Ok(CanvasResponse::Multiple(arr)),
            single => Ok(CanvasResponse::Single(single)),
        }
    }

    async fn handle_error_response(&self, response: Response) -> CanvasError {
        let status_code = response.status().as_u16();
        let error_text = response.text().await.unwrap();

        let error_message = if let Ok(error_json) = from_str::<Value>(&error_text) {
            if let Some(errors) = error_json.get("errors") {
                match errors {
                    Value::Object(obj) => obj
                        .get("message")
                        .and_then(|v| v.as_str())
                        .unwrap_or(&error_text)
                        .to_string(),

                    Value::Array(arr) => {
                        if let Some(first_error) = arr.first() {
                            first_error.as_str().unwrap_or(&error_text).to_string()
                        } else {
                            error_text
                        }
                    }
                    _ => error_text,
                }
            } else if let Some(message) = error_json.get("message") {
                message.as_str().unwrap_or(&error_text).to_string()
            } else {
                error_text
            }
        } else {
            error_text
        };

        CanvasError::Api {
            status_code,
            message: error_message,
        }
    }
}
