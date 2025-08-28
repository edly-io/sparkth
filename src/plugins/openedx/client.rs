use reqwest::{Client, Method, Response};
use serde_json::{Value, from_str};
use url::Url;

use crate::plugins::{
    errors::LMSError,
    request::{Auth, request},
    response::LMSResponse,
};

#[derive(Debug, Clone)]
pub struct OpenEdxClient {
    lms_url: String,
    studio_url: String,
    client_id: String,
    client: Client,
    access_token: Option<String>,
    username: Option<String>,
}

impl OpenEdxClient {
    pub fn new(lms_url: &str, studio_url: &str, access_token: Option<String>) -> Self {
        Self {
            lms_url: lms_url.trim_end_matches('/').to_string(),
            studio_url: studio_url.trim_end_matches('/').to_string(),
            client_id: "login-service-client-id".to_string(),
            client: Client::new(),
            access_token,
            username: None,
        }
    }

    pub async fn get_token(&mut self, username: &str, password: &str) -> Result<String, LMSError> {
        let auth_url = format!("{}/oauth2/access_token", self.lms_url);
        let form = [
            ("client_id", self.client_id.as_str()),
            ("grant_type", "password"),
            ("token_type", "jwt"),
            ("username", username),
            ("password", password),
        ];
        let resp = self.client.post(&auth_url).form(&form).send().await?;
        if !resp.status().is_success() {
            return Err(self.handle_error_response(resp).await);
        }
        let auth_json: Value = from_str(&resp.text().await?)?;
        let token = auth_json
            .get("access_token")
            .and_then(|v| v.as_str())
            .ok_or_else(|| LMSError::Authentication("missing access_token".into()))?
            .to_string();

        self.access_token = Some(token.clone());

        Ok(token)
    }

    pub async fn openedx_authenticate(&self, access_token: &str) -> Result<Value, LMSError> {
        let me_url = format!("{}/api/user/v1/me", self.lms_url);

        let resp = self
            .client
            .request(Method::GET, &me_url)
            .bearer_auth(access_token)
            .send()
            .await?;

        if !resp.status().is_success() {
            return Err(self.handle_error_response(resp).await);
        }

        let text = resp.text().await?;
        if text.is_empty() {
            return Ok(Value::Object(serde_json::Map::new()));
        }
        Ok(from_str(&text)?)
    }

    async fn handle_error_response(&self, response: Response) -> LMSError {
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
        LMSError::Api {
            status_code,
            message,
        }
    }

    // Studio-style auth (e.g., /api/v1/course_runs/)
    pub async fn request_jwt(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<LMSResponse, LMSError> {
        let token = self
            .access_token
            .as_ref()
            .ok_or_else(|| LMSError::Authentication("Access token not set".into()))?;

        let url = Url::parse(&format!("{}/{endpoint}", self.studio_url))?;
        request(Auth::Jwt, token, http_method, url, payload, &self.client).await
    }

    pub fn username(&self) -> Option<&str> {
        self.username.as_deref()
    }
}
