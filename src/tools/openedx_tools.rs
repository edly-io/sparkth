use reqwest::Method;
use rmcp::{
    ErrorData,
    handler::server::tool::Parameters,
    model::{CallToolResult, Content, ErrorCode},
    tool, tool_router,
};
use serde_json::{Value, json, to_value};
use url::Url;

use crate::plugins::openedx::types::{OpenEdxAccessTokenPayload, OpenEdxAuthenticationPayload, OpenEdxCreateCourseArgs, OpenEdxCreateProblemOrHtmlArgs, OpenEdxListCourseRunsArgs, OpenEdxResponse, OpenEdxXBlockPayload};
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
    
    async fn openedx_create_basic_component(
        &self,
        auth: &OpenEdxAccessTokenPayload,
        course_id: &str,
        unit_locator: &str,
        kind: &str,            // "problem" | "html"
        display_name: &str,
    ) -> Result<String, ErrorData> {
        if kind != "problem" && kind != "html" {
            return Err(ErrorData::new(
                ErrorCode::INVALID_PARAMS,
                "kind must be 'problem' or 'html'",
                None,
            ));
        }

        let studio = auth.studio_url.trim_end_matches('/').to_string();
        let client = OpenEdxClient::new(&auth.lms_url, &studio, Some(auth.access_token.clone()));
        let create_url = Url::parse(&format!("{}/api/contentstore/v0/xblock/{}", studio, course_id))
            .map_err(|e| ErrorData::new(ErrorCode::INVALID_PARAMS, e.to_string(), None))?;

        let payload = json!({
            "category": kind,
            "parent_locator": unit_locator,
            "display_name": display_name
        });

        let created = client
            .request_jwt(Method::POST, create_url, Some(payload))
            .await
            .map_err(|e| ErrorData::new(ErrorCode::INTERNAL_ERROR, format!("Create component failed: {e}"), None))?;

        let locator = match created {
            OpenEdxResponse::Single(ref v) => v
                .get("locator")
                .or_else(|| v.get("usage_key"))
                .or_else(|| v.get("id"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
            OpenEdxResponse::Multiple(ref arr) => arr.first()
                .and_then(|v| v.get("locator").or_else(|| v.get("usage_key")).or_else(|| v.get("id")))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
        }.ok_or_else(|| ErrorData::new(
            ErrorCode::INTERNAL_ERROR,
            "Server did not return a new block locator",
            None,
        ))?;

        Ok(locator)
    }

    async fn openedx_update_xblock_content(
        &self,
        auth: &OpenEdxAccessTokenPayload,
        course_id: &str,
        locator: &str,
        data: Option<String>,    // OLX for problem; HTML for html component
        metadata: Option<Value>, // e.g. {"display_name":"...", "weight":1}
    ) -> Result<OpenEdxResponse, ErrorData> {
        if data.is_none() && metadata.is_none() {
            return Err(ErrorData::new(
                ErrorCode::INVALID_PARAMS,
                "Nothing to update: provide `data` and/or `metadata`",
                None,
            ));
        }

        let studio = auth.studio_url.trim_end_matches('/').to_string();
        let client = OpenEdxClient::new(&auth.lms_url, &studio, Some(auth.access_token.clone()));

        let encoded: String = form_urlencoded::byte_serialize(locator.as_bytes()).collect();
        let update_url = Url::parse(&format!(
            "{}/api/contentstore/v0/xblock/{}/{}",
            studio, course_id, encoded
        ))
            .map_err(|e| ErrorData::new(ErrorCode::INVALID_PARAMS, e.to_string(), None))?;

        let mut body = serde_json::Map::new();
        if let Some(d) = data { body.insert("data".to_string(), Value::String(d)); }
        if let Some(m) = metadata { body.insert("metadata".to_string(), m); }
        let payload = Value::Object(body);

        match client.request_jwt(Method::PUT, update_url.clone(), Some(payload.clone())).await {
            Ok(r) => Ok(r),
            Err(e1) => client
                .request_jwt(Method::PATCH, update_url, Some(payload))
                .await
                .map_err(|e2| ErrorData::new(
                    ErrorCode::INTERNAL_ERROR,
                    format!("Update failed (PUT and PATCH): {e1}; {e2}"),
                    None,
                )),
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
        description = "Create an XBlock (chapter/section, sequential/subsection, vertical/unit). 
The parent locator for should be in the format `block-v1:ORG+COURSE+RUN+type@course+block@course`.
Don't proceed if user is not authenticated."
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

    #[tool(
        description = "Create a Problem or HTML. The HTML component should be in the same unit, while the Problem component should be in a separate unit.
Then immediately update the component with content.\n\
• `kind`: \"problem\" (OLX problem) or \"html\" (HTML component). Default: \"problem\".\n\
• Provide `data` with OLX/HTML to fully control content, OR set `mcq_boilerplate=true` (for problems) to use a minimal MCQ template.\n\
• Optional `metadata` supports fields like `display_name`, `weight`, `max_attempts`, etc.\n\
• Minimal MCQ OLX template used when `mcq_boilerplate=true` and no `data`:\n\
<problem>\n  <p>Your question here</p>\n  <multiplechoiceresponse>\n    <choicegroup type=\"MultipleChoice\" shuffle=\"true\">\n      <choice correct=\"true\">Correct</choice>\n      <choice correct=\"false\">Incorrect</choice>\n    </choicegroup>\n  </multiplechoiceresponse>\n</problem>"
    )]
    pub async fn openedx_create_problem_or_html(
        &self,
        Parameters(OpenEdxCreateProblemOrHtmlArgs {
                       auth,
                       course_id,
                       unit_locator,
                       kind,
                       display_name,
                       data,
                       metadata,
                       mcq_boilerplate,
                   }): Parameters<OpenEdxCreateProblemOrHtmlArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let k = kind.unwrap_or_else(|| "problem".into());
        let name = display_name.unwrap_or_else(|| if k == "problem" { "New Problem" } else { "New HTML" }.into());

        // 1) Create base component
        let locator = self
            .openedx_create_basic_component(&auth, &course_id, &unit_locator, &k, &name)
            .await?;

        // 2) Choose content to update with
        let final_data = if data.is_some() {
            data
            } else if k == "problem" && mcq_boilerplate.unwrap_or(false) {
                Some(r#"<problem>
                  <p>Your question here</p>
                  <multiplechoiceresponse>
                    <choicegroup type="MultipleChoice" shuffle="true">
                      <choice correct="true">Correct</choice>
                      <choice correct="false">Incorrect</choice>
                    </choicegroup>
                  </multiplechoiceresponse>
                </problem>"#.to_string())
        } else {
            None
        };

        // 3) Update (if we have content and/or metadata)
        let result_value = if final_data.is_some() || metadata.is_some() {
            let updated = self
                .openedx_update_xblock_content(&auth, &course_id, &locator, final_data, metadata)
                .await?;

            match updated {
                OpenEdxResponse::Single(v) => v,
                OpenEdxResponse::Multiple(arr) => Value::Array(arr),
            }
        } else {
            json!({"detail": "Component created; no content/metadata to update"})
        };

        let out = json!({ "locator": locator, "result": result_value });
        Ok(CallToolResult::success(vec![Content::text(out.to_string())]))
    }
}
