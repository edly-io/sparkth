use reqwest::Method;
use rmcp::{
    ErrorData,
    handler::server::tool::Parameters,
    model::{CallToolResult, Content, ErrorCode},
    tool, tool_router,
};
use serde_json::{Value, to_value};

use crate::{
    plugins::openedx::client::OpenEdxClient,
    server::mcp_server::SparkthMCPServer,
};

#[derive(serde::Deserialize, schemars::JsonSchema)]
pub struct OpenEdxAuthenticationPayload {
    pub url: String,
    pub username: String,
    pub password: String,
}

impl SparkthMCPServer {
    fn openedx_handle_response_single(&self, value: Value) -> CallToolResult {
        CallToolResult::success(vec![Content::text(value.to_string())])
    }

    fn openedx_handle_response_vec(&self, value: Value) -> CallToolResult {
        match value {
            Value::Array(arr) => {
                let s: Vec<String> = arr.into_iter().map(|v| v.to_string()).collect();
                CallToolResult::success(vec![Content::text(s.join(","))])
            }
            other => CallToolResult::success(vec![Content::text(other.to_string())]),
        }
    }
}

#[tool_router(router = openedx_tools_router, vis = "pub")]
impl SparkthMCPServer {
    #[tool(description = "Store the LMS URL and credentials; fetch an access token and validate it")]
    pub async fn authenticate_user_openedx(
        &self,
        Parameters(OpenEdxAuthenticationPayload { url, username, password }): Parameters<OpenEdxAuthenticationPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let mut client = OpenEdxClient::new(url);
        match client.get_token(&username, &password).await {
            Ok(_token) => {
                let who = client.username().unwrap_or(&username);
                Ok(CallToolResult::success(vec![
                    Content::text(format!("Successfully authenticated as {who}")),
                ]))
            }
            Err(err) => {
                let msg = format!("Open edX authentication failed: {err}");
                Err(ErrorData::new(ErrorCode::RESOURCE_NOT_FOUND, msg, None))
            }
        }
    }

    #[tool(description = "Get current Open edX user info after authentication")]
    pub async fn openedx_get_user_info(
        &self,
        Parameters(OpenEdxAuthenticationPayload { url, username, password }): Parameters<OpenEdxAuthenticationPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let mut client = OpenEdxClient::new(url);
        client.get_token(&username, &password).await.map_err(|e| {
            ErrorData::new(ErrorCode::RESOURCE_NOT_FOUND, format!("Auth failed: {e}"), None)
        })?;
        match client.get_user_info().await {
            Ok(json) => Ok(self.openedx_handle_response_single(json)),
            Err(e) => Err(ErrorData::new(
                ErrorCode::INTERNAL_ERROR,
                format!("Fetching user info failed: {e}"),
                None,
            )),
        }
    }
}