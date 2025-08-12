use reqwest::{Client, Method, Response};
use serde_json::{Value, from_str};

use crate::plugins::openedx::{error::OpenEdxError, types::OpenEdxResponse};

#[derive(Debug, Clone)]
pub struct OpenEdxClient {
    base_url: String,
    client_id: String,
    client: Client,
    access_token: Option<String>,
    username: Option<String>,
}

impl OpenEdxClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into().trim_end_matches('/').to_string(),
            client_id: "login-service-client-id".to_string(),
            client: Client::new(),
            access_token: None,
            username: None,
        }
    }
    pub fn with_client_id(base_url: impl Into<String>, client_id: impl Into<String>) -> Self {
        Self {
            client_id: client_id.into(),
            ..Self::new(base_url)
        }
    }

    pub async fn get_token(
        &mut self,
        username: impl AsRef<str>,
        password: impl AsRef<str>,
    ) -> Result<String, OpenEdxError> {
        let auth_url = format!("{}/oauth2/access_token", self.base_url);
        let form = [
            ("client_id", self.client_id.as_str()),
            ("grant_type", "password"),
            ("username", username.as_ref()),
            ("password", password.as_ref()),
        ];
        let resp = self.client.post(&auth_url).form(&form).send().await?;
        if !resp.status().is_success() {
            return Err(self.handle_error_response(resp).await);
        }
        let auth_json: Value = from_str(&resp.text().await?)?;
        let token = auth_json
            .get("access_token")
            .and_then(|v| v.as_str())
            .ok_or_else(|| OpenEdxError::Authentication("missing access_token".into()))?
            .to_string();

        self.access_token = Some(token.clone());

        // Validate by fetching user info
        let me = self.get_user_info().await?;
        self.username = me.get("username").and_then(|v| v.as_str()).map(|s| s.to_string());

        Ok(token)
    }

    pub async fn get_user_info(&self) -> Result<Value, OpenEdxError> {
        let token = self
            .access_token
            .as_ref()
            .ok_or_else(|| OpenEdxError::Authentication("API token not set".into()))?;

        let url = format!("{}/api/user/v1/me", self.base_url);
        let resp = self.client.request(Method::GET, &url).bearer_auth(token).send().await?;
        if !resp.status().is_success() {
            return Err(self.handle_error_response(resp).await);
        }
        let text = resp.text().await?;
        if text.is_empty() {
            return Ok(Value::Object(serde_json::Map::new()));
        }
        Ok(from_str(&text)?)
    }

    async fn handle_error_response(&self, response: Response) -> OpenEdxError {
        let status_code = response.status().as_u16();
        let text = response.text().await.unwrap_or_default();
        let message = if let Ok(json) = from_str::<Value>(&text) {
            json.get("error_description")
                .or_else(|| json.get("developer_message"))
                .or_else(|| json.get("detail"))
                .or_else(|| json.get("message"))
                .and_then(|v| v.as_str())
                .unwrap_or(&text)
                .to_string()
        } else {
            text
        };
        OpenEdxError::Api { status_code, message }
    }

    pub fn token(&self) -> Option<&str> { self.access_token.as_deref() }
    pub fn username(&self) -> Option<&str> { self.username.as_deref() }
    pub fn base_url(&self) -> &str { &self.base_url }
}