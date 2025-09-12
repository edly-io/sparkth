use reqwest::{Client, Method, Response};
use serde_json::{Value, from_str, to_value};
use url::Url;
use bytes::Bytes;
use crate::plugins::{
    errors::LMSError,
    request::{Auth, request},
    response::LMSResponse,
    openedx::{
        types::TokenResponse,
    }
};


#[derive(Debug, Clone)]
pub struct OpenEdxClient {
    lms_url: String,
    client_id: String,
    client: Client,
    access_token: Option<String>,
    refresh_token: Option<String>,
    username: Option<String>,
}

impl OpenEdxClient {
    pub fn new(lms_url: &str, access_token: Option<String>) -> Self {
        Self {
            lms_url: lms_url.trim_end_matches('/').to_string(),
            client_id: "login-service-client-id".to_string(),
            client: Client::new(),
            access_token,
            refresh_token: None,
            username: None,
        }
    }
    pub async fn get_token(&mut self, username: &str, password: &str) -> Result<Value, LMSError> {
        let auth_url = format!("{}/oauth2/access_token", self.lms_url.trim_end_matches('/'));
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

        let bytes: Bytes = resp.bytes().await?;
        let tr: TokenResponse = serde_json::from_slice(&bytes)
            .map_err(|e| LMSError::Other(format!("failed parsing auth JSON: {e}")))?;

        if tr.access_token.trim().is_empty() {
            return Err(LMSError::Authentication("empty access_token".into()));
        }

        // Persist tokens
        self.access_token = Some(tr.access_token.clone());
        self.refresh_token = tr.refresh_token.clone();

        // Return full JSON
        let full = to_value(tr).map_err(|e| LMSError::Other(format!("failed serializing token JSON: {e}")))?;
        Ok(full)
    }

    pub async fn refresh_access_token(&mut self, refresh_token: &str) -> Result<Value, LMSError> {
        let auth_url = format!("{}/oauth2/access_token", self.lms_url.trim_end_matches('/'));
        let form = [
            ("client_id", self.client_id.as_str()),
            ("grant_type", "refresh_token"),
            ("token_type", "jwt"),
            ("refresh_token", refresh_token),
        ];

        let resp = self.client.post(&auth_url).form(&form).send().await?;
        if !resp.status().is_success() {
            return Err(self.handle_error_response(resp).await);
        }

        let bytes: Bytes = resp.bytes().await?;
        let tr: TokenResponse = serde_json::from_slice(&bytes)
            .map_err(|e| LMSError::Other(format!("failed parsing refresh JSON: {e}")))?;

        if tr.access_token.trim().is_empty() {
            return Err(LMSError::Authentication("empty access_token".into()));
        }
        self.access_token = Some(tr.access_token.clone());
        self.refresh_token = tr
            .refresh_token
            .clone()
            .or_else(|| Some(refresh_token.to_string()));

        let full = to_value(tr)
            .map_err(|e| LMSError::Other(format!("failed serializing refresh JSON: {e}")))?;
        Ok(full)
    }

    pub async fn openedx_authenticate(&self) -> Result<LMSResponse, LMSError> {
        self.request_jwt(Method::GET, "api/user/v1/me", None, None, &self.lms_url)
            .await
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
        params: Option<Value>,
        payload: Option<Value>,
        base_url: &str,
    ) -> Result<LMSResponse, LMSError> {
        let token = self
            .access_token
            .as_ref()
            .ok_or_else(|| LMSError::Authentication("Access token not set".into()))?;

        let url = Url::parse(&format!("{}/{endpoint}", base_url))?;
        request(
            Auth::Jwt,
            token,
            http_method,
            url,
            params,
            payload,
            &self.client,
        )
        .await
    }

    pub fn username(&self) -> Option<&str> {
        self.username.as_deref()
    }
}
