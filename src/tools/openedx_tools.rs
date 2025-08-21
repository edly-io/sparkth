use reqwest::Method;
use rmcp::{
    ErrorData,
    handler::server::tool::Parameters,
    model::{CallToolResult, Content, ErrorCode},
    tool, tool_router,
};
use serde_json::{Value, json, to_value};
use url::Url;

use crate::plugins::openedx::types::{
    OpenEdxAccessTokenPayload, OpenEdxAuthenticationPayload, OpenEdxCreateCourseArgs,
    OpenEdxListCourseRunsArgs, OpenEdxResponse, OpenEdxXBlockPayload,
};
use crate::{plugins::openedx::client::OpenEdxClient, server::mcp_server::SparkthMCPServer};

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
    #[tool(
        description = "Store the LMS URL and credentials; fetch an access token and validate it"
    )]
    pub async fn openedx_authenticate_user(
        &self,
        Parameters(OpenEdxAuthenticationPayload {
            lms_url,
            studio_url,
            username,
            password,
        }): Parameters<OpenEdxAuthenticationPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let mut client = OpenEdxClient::new(&lms_url, &studio_url, None);
        match client.get_token(&username, &password).await {
            Ok(token) => {
                let who = client.username().unwrap_or(&username);
                let body = json!({
                    "access_token": token,
                    "message": format!("Successfully authenticated as {who}")
                });
                Ok(CallToolResult::success(vec![Content::text(
                    body.to_string(),
                )]))
            }
            Err(err) => {
                let msg = format!("Open edX authentication failed: {err}");
                Err(ErrorData::new(ErrorCode::RESOURCE_NOT_FOUND, msg, None))
            }
        }
    }

    #[tool(
        description = "Fetch current Open edX user info (/api/user/v1/me) using an existing access token"
    )]
    pub async fn openedx_get_user_info(
        &self,
        Parameters(OpenEdxAccessTokenPayload {
            lms_url,
            studio_url,
            access_token,
        }): Parameters<OpenEdxAccessTokenPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = OpenEdxClient::new(&lms_url, &studio_url, Some(access_token.clone()));
        match client.openedx_authenticate(&access_token).await {
            Ok(json) => Ok(self.openedx_handle_response_single(json)),
            Err(e) => Err(ErrorData::new(
                ErrorCode::INTERNAL_ERROR,
                format!("Fetching user info failed: {e}"),
                None,
            )),
        }
    }

    #[tool(description = "Create an Open edX course run. Authenticate the user first ")]
    pub async fn openedx_create_course_run(
        &self,
        Parameters(OpenEdxCreateCourseArgs { auth, course }): Parameters<OpenEdxCreateCourseArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = OpenEdxClient::new(
            &auth.lms_url,
            &auth.studio_url,
            Some(auth.access_token.clone()),
        );

        let create_url = format!("{}/api/v1/course_runs/", auth.studio_url);
        let url = Url::parse(&create_url).unwrap();

        match client
            .request_jwt(Method::POST, url, Some(to_value(course).unwrap()))
            .await
        {
            Ok(OpenEdxResponse::Single(v)) => Ok(self.openedx_handle_response_single(v)),
            Ok(OpenEdxResponse::Multiple(arr)) => {
                Ok(self.openedx_handle_response_vec(Value::Array(arr)))
            }
            Err(e) => Err(ErrorData::new(
                ErrorCode::INTERNAL_ERROR,
                format!("List course runs failed: {e}"),
                None,
            )),
        }
    }

    #[tool(description = "List Open edX course runs. Don't proceed if user is not authenticated.")]
    pub async fn openedx_list_course_runs(
        &self,
        Parameters(OpenEdxListCourseRunsArgs {
            auth,
            page,
            page_size,
        }): Parameters<OpenEdxListCourseRunsArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let lms = auth.lms_url.trim_end_matches('/').to_string();
        let studio = auth.studio_url.trim_end_matches('/').to_string();
        let client = OpenEdxClient::new(&lms, &studio, Some(auth.access_token));

        let p = page.unwrap_or(1);
        let ps = page_size.unwrap_or(20);
        let endpoint = format!("{}/api/v1/course_runs/?page={}&page_size={}", studio, p, ps);
        let url = Url::parse(&endpoint).unwrap();

        match client.request_jwt(Method::GET, url, None).await {
            Ok(OpenEdxResponse::Single(v)) => Ok(self.openedx_handle_response_single(v)),
            Ok(OpenEdxResponse::Multiple(arr)) => {
                Ok(self.openedx_handle_response_vec(Value::Array(arr)))
            }
            Err(e) => Err(ErrorData::new(
                ErrorCode::INTERNAL_ERROR,
                format!("List course runs failed: {e}"),
                None,
            )),
        }
    }

    #[tool(
        description = "Create an XBlock (chapter/section, sequential/subsection, vertical/unit). Don't proceed if user is not authenticated."
    )]
    pub async fn openedx_create_xblock(
        &self,
        Parameters(OpenEdxXBlockPayload {
            auth,
            xblock,
            course_id,
        }): Parameters<OpenEdxXBlockPayload>,
    ) -> Result<CallToolResult, ErrorData> {
        let client = OpenEdxClient::new(&auth.lms_url, &auth.studio_url, Some(auth.access_token));

        let endpoint = format!(
            "{}/api/contentstore/v0/xblock/{}",
            auth.studio_url, course_id
        );
        let url = Url::parse(&endpoint).unwrap();

        match client
            .request_jwt(Method::POST, url, Some(to_value(xblock).unwrap()))
            .await
        {
            Ok(OpenEdxResponse::Single(v)) => Ok(self.openedx_handle_response_single(v)),
            Ok(OpenEdxResponse::Multiple(arr)) => {
                Ok(self.openedx_handle_response_vec(Value::Array(arr)))
            }
            Err(e) => Err(ErrorData::new(
                ErrorCode::INTERNAL_ERROR,
                format!("XBlock creation failed: {e}"),
                None,
            )),
        }
    }
}
