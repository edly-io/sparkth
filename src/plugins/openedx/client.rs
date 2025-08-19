use reqwest::{Client, Method, Response};
use serde_json::{Value, from_str};

use crate::plugins::openedx::{error::OpenEdxError, types::OpenEdxResponse};

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
    pub fn new(lms_url: impl Into<String>, studio_url: impl Into<String>) -> Self {
        Self {
            lms_url: lms_url.into().trim_end_matches('/').to_string(),
            studio_url: studio_url.into().trim_end_matches('/').to_string(),
            client_id: "login-service-client-id".to_string(),
            client: Client::new(),
            access_token: None,
            username: None,
        }
    }

    pub async fn get_token(
        &mut self,
        username: impl AsRef<str>,
        password: impl AsRef<str>,
    ) -> Result<String, OpenEdxError> {
        let auth_url = format!("{}/oauth2/access_token", self.lms_url);
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

        Ok(token)
    }

    pub async fn openedx_authenticate(
        &self,
        access_token: impl AsRef<str>,
    ) -> Result<Value, OpenEdxError> {
        let me_url = format!("{}/api/user/v1/me", self.lms_url);

        let resp = self
            .client
            .request(Method::GET, &me_url)
            .bearer_auth(access_token.as_ref())
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

    /// LMS-style auth (e.g., /api/user/v1/me)
    pub async fn request_bearer(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<OpenEdxResponse, OpenEdxError> {
        self.request_with_auth("Bearer", http_method, endpoint, payload).await
    }

    /// Studio-style auth (e.g., /api/v1/course_runs/)
    pub async fn request_jwt(
        &self,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<OpenEdxResponse, OpenEdxError> {
        self.request_with_auth("JWT", http_method, endpoint, payload).await
    }

    async fn request_with_auth(
        &self,
        auth_prefix: &str,
        http_method: Method,
        endpoint: &str,
        payload: Option<Value>,
    ) -> Result<OpenEdxResponse, OpenEdxError> {
        let token = self
            .access_token
            .as_ref()
            .ok_or_else(|| OpenEdxError::Authentication("API token not set".into()))?;



        let url = if endpoint.starts_with("http") {
            endpoint.to_string()
        } else {
            format!("{}/{}", self.lms_url, endpoint.trim_start_matches('/'))
        };

        let mut req = self
            .client
            .request(http_method, &url)
            .header("Authorization", format!("{auth_prefix} {token}"));

        if let Some(p) = payload {
            req = req.json(&p);
        }

        let resp = req.send().await?;
        if !resp.status().is_success() {
            return Err(self.handle_error_response(resp).await);
        }

        let text = resp.text().await?;
        if text.is_empty() {
            return Ok(OpenEdxResponse::Single(Value::Object(serde_json::Map::new())));
        }

        let json_value: Value = from_str(&text)?;
        Ok(match json_value {
            Value::Array(arr) => OpenEdxResponse::Multiple(arr),
            single => OpenEdxResponse::Single(single),
        })
    }

    pub fn token(&self) -> Option<&str> { self.access_token.as_deref() }
    pub fn username(&self) -> Option<&str> { self.username.as_deref() }
    pub fn lms_url(&self) -> &str { &self.lms_url }
    pub fn studio_url(&self) -> &str { &self.studio_url }
}
