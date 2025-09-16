use reqwest::Method;
use rmcp::{handler::server::wrapper::Parameters, tool, tool_router};
use serde_json::{Value, json, to_value};

use crate::plugins::openedx::types::OpenEdxRefreshTokenPayload;
use crate::{
    plugins::{
        errors::LMSError,
        openedx::{
            client::OpenEdxClient,
            types::{
                OpenEdxAuth, OpenEdxCourseTreeRequest, OpenEdxLMSAccess, OpenEdxUpdateXBlockPayload,
            },
        },
    },
    server::mcp_server::SparkthMCPServer,
};
use crate::{
    plugins::{
        openedx::types::{
            Component, OpenEdxAccessTokenPayload, OpenEdxCreateCourseArgs,
            OpenEdxCreateProblemOrHtmlArgs, OpenEdxGetBlockContentArgs, OpenEdxListCourseRunsArgs,
            OpenEdxXBlockPayload,
        },
        response::LMSResponse,
    },
    utils::cached_schema_for_type,
};

impl SparkthMCPServer {
    async fn openedx_create_basic_component(
        &self,
        auth: &OpenEdxAccessTokenPayload,
        course_id: &str,
        unit_locator: &str,
        kind: &Component,
        display_name: &str,
    ) -> Result<String, LMSError> {
        let studio = auth.studio_url.trim_end_matches('/').to_string();
        let client = OpenEdxClient::new(&auth.lms_url, Some(auth.access_token.clone()));
        let create_url = format!("api/contentstore/v0/xblock/{course_id}");

        let payload = json!({
            "category": kind,
            "parent_locator": unit_locator,
            "display_name": display_name
        });

        let created = client
            .request_jwt(Method::POST, &create_url, None, Some(payload), &studio)
            .await?;

        let locator = match created {
            LMSResponse::Single(ref v) => v
                .get("locator")
                .or_else(|| v.get("usage_key"))
                .or_else(|| v.get("id"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
            LMSResponse::Multiple(ref arr) => arr
                .first()
                .and_then(|v| {
                    v.get("locator")
                        .or_else(|| v.get("usage_key"))
                        .or_else(|| v.get("id"))
                })
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
        }
        .ok_or_else(|| {
            LMSError::InternalServerError("Server did not return a new block locator".to_string())
        })?;

        Ok(locator)
    }

    async fn openedx_update_xblock_content(
        &self,
        auth: &OpenEdxAccessTokenPayload,
        course_id: &str,
        locator: &str,
        data: Option<String>,    // OLX for problem; HTML for html component
        metadata: Option<Value>, // e.g. {"display_name":"...", "weight":1}
    ) -> Result<LMSResponse, String> {
        if data.is_none() && metadata.is_none() {
            return Err(LMSError::InvalidParams(
                "Nothing to update: provide `data` and/or `metadata`".to_string(),
            )
            .to_string());
        }

        let studio = auth.studio_url.trim_end_matches('/').to_string();
        let client = OpenEdxClient::new(&auth.lms_url, Some(auth.access_token.clone()));

        let encoded: String = form_urlencoded::byte_serialize(locator.as_bytes()).collect();
        let endpoint = format!("api/contentstore/v0/xblock/{course_id}/{encoded}");

        let mut body = serde_json::Map::new();
        if let Some(d) = data {
            body.insert("data".to_string(), Value::String(d));
        }
        if let Some(m) = metadata {
            body.insert("metadata".to_string(), m);
        }
        let payload = Value::Object(body);

        let res = client
            .request_jwt(
                Method::PATCH,
                &endpoint,
                None,
                Some(payload.clone()),
                &studio,
            )
            .await
            .map_err(|err| err.to_string())?;

        Ok(res)
    }
}

#[tool_router(router = openedx_tools_router, vis = "pub")]
impl SparkthMCPServer {
    #[tool(
        description = "Store the LMS URL and credentials; fetch an access token and validate it",
        input_schema = cached_schema_for_type::<OpenEdxAuth>()
    )]
    pub async fn openedx_authenticate(
        &self,
        Parameters(OpenEdxAuth {
            lms_url,
            studio_url,
            username,
            password,
        }): Parameters<OpenEdxAuth>,
    ) -> Result<String, String> {
        let mut client = OpenEdxClient::new(&lms_url, None);

        client
            .get_token(&username, &password)
            .await
            .map(|auth_json| {
                let who = client.username().unwrap_or(&username);
                let access_token = auth_json
                    .get("access_token")
                    .and_then(|v| v.as_str())
                    .unwrap_or_default();
                let refresh_token = auth_json.get("refresh_token").and_then(|v| v.as_str());

                json!({
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "studio_url": studio_url,
                    "message": format!("Successfully authenticated as {who}")
                })
                .to_string()
            })
            .map_err(|err| format!("Open edX authentication failed: {err}"))
    }

    #[tool(
    description = "Refresh an Open edX JWT using a refresh_token and return the new tokens\
    - Use this when the you are getting Unauthorized errors from other endpoints if you have a refresh token.\
    ",
    input_schema = cached_schema_for_type::<OpenEdxRefreshTokenPayload>()
    )]
    pub async fn openedx_refresh_access_token(
        &self,
        Parameters(OpenEdxRefreshTokenPayload {
            lms_url,
            studio_url,
            refresh_token,
        }): Parameters<OpenEdxRefreshTokenPayload>,
    ) -> Result<String, String> {
        let mut client = OpenEdxClient::new(&lms_url, None);

        client
            .refresh_access_token(&refresh_token)
            .await
            .map(|auth_json| {
                let access_token = auth_json
                    .get("access_token")
                    .and_then(|v| v.as_str())
                    .unwrap_or_default();

                let new_refresh = auth_json
                    .get("refresh_token")
                    .and_then(|v| v.as_str())
                    .unwrap_or(&refresh_token);
                json!({
                    "access_token": access_token,
                    "refresh_token": new_refresh,
                    "studio_url": studio_url,
                    "message": "Access token refreshed"
                })
                .to_string()
            })
            .map_err(|err| format!("Open edX refresh failed: {err}"))
    }

    #[tool(
        description = "Fetch current Open edX user info (/api/user/v1/me) using an existing access token",
        input_schema = cached_schema_for_type::<OpenEdxLMSAccess>()
    )]
    pub async fn openedx_get_user_info(
        &self,
        Parameters(OpenEdxLMSAccess {
            lms_url,
            access_token,
        }): Parameters<OpenEdxLMSAccess>,
    ) -> Result<String, String> {
        let client = OpenEdxClient::new(&lms_url, Some(access_token.clone()));
        client
            .openedx_authenticate()
            .await
            .map(|res| self.handle_response_single(res))
            .map_err(|err| format!("Get user info failed: {err}"))
    }

    #[tool(description = "Create an Open edX course run. Authenticate the user first.",
        input_schema = cached_schema_for_type::<OpenEdxCreateCourseArgs>()
    )]
    pub async fn openedx_create_course_run(
        &self,
        Parameters(OpenEdxCreateCourseArgs { auth, course }): Parameters<OpenEdxCreateCourseArgs>,
    ) -> Result<String, String> {
        let client = OpenEdxClient::new(&auth.lms_url, Some(auth.access_token.clone()));

        client
            .request_jwt(
                Method::POST,
                "/api/v1/course_runs/",
                None,
                Some(to_value(course).unwrap()),
                &auth.studio_url,
            )
            .await
            .map(|response| self.handle_response_single(response))
            .map_err(|err| format!("Create course runs failed: {err}"))
    }

    #[tool(description = "List Open edX course runs. Don't proceed if user is not authenticated.",
        input_schema = cached_schema_for_type::<OpenEdxListCourseRunsArgs>()
    )]
    pub async fn openedx_list_course_runs(
        &self,
        Parameters(OpenEdxListCourseRunsArgs {
            auth,
            page,
            page_size,
        }): Parameters<OpenEdxListCourseRunsArgs>,
    ) -> Result<String, String> {
        let lms = auth.lms_url.trim_end_matches('/').to_string();
        let studio = auth.studio_url.trim_end_matches('/').to_string();
        let client = OpenEdxClient::new(&lms, Some(auth.access_token));

        let p = page.unwrap_or(1);
        let ps = page_size.unwrap_or(20);
        let endpoint = format!("api/v1/course_runs/?page={p}&page_size={ps}");

        client
            .request_jwt(Method::GET, &endpoint, None, None, &studio)
            .await
            .map(|response| self.handle_response_vec(response))
            .map_err(|e| format!("List course runs failed: {e}"))
    }

    #[tool(
        description = "Create an XBlock (chapter/section, sequential/subsection, vertical/unit).
The parent locator for should be in the format `block-v1:ORG+COURSE+RUN+type@course+block@course`.
Don't proceed if user is not authenticated.",
        input_schema = cached_schema_for_type::<OpenEdxXBlockPayload>()
    )]
    pub async fn openedx_create_xblock(
        &self,
        Parameters(OpenEdxXBlockPayload {
            auth,
            xblock,
            course_id,
        }): Parameters<OpenEdxXBlockPayload>,
    ) -> Result<String, String> {
        let client = OpenEdxClient::new(&auth.lms_url, Some(auth.access_token));

        let endpoint = format!("api/contentstore/v0/xblock/{course_id}");

        client
            .request_jwt(
                Method::POST,
                &endpoint,
                None,
                Some(to_value(xblock).unwrap()),
                &auth.studio_url,
            )
            .await
            .map(|response| self.handle_response_single(response))
            .map_err(|err| format!("XBlock creation failed: {err}"))
    }

    #[tool(
        description = "Create a Problem or HTML. The HTML component should be in the same unit, while the Problem component should be in a separate unit.
Then immediately call the update Xblock tool to update the XBlock.\n\
• `kind`: \"problem\" (OLX problem) or \"html\" (HTML component). Default: \"problem\".\n\
• Provide `data` with OLX/HTML to fully control content, OR set `mcq_boilerplate=true` (for problems) to use a minimal MCQ template.\n\
• Optional `metadata` supports fields like `display_name`, `weight`, `max_attempts`, etc.\n\
• Minimal MCQ OLX template used when `mcq_boilerplate=true` and no `data`:\n\
<problem>\n  <p>Your question here</p>\n  <multiplechoiceresponse>\n    <choicegroup type=\"MultipleChoice\" shuffle=\"true\">\n      <choice correct=\"true\">Correct</choice>\n      <choice correct=\"false\">Incorrect</choice>\n    </choicegroup>\n  </multiplechoiceresponse>\n</problem>",
        input_schema = cached_schema_for_type::<OpenEdxCreateProblemOrHtmlArgs>()
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
    ) -> Result<String, String> {
        let component = kind.unwrap_or(Component::Problem);
        let name = display_name.unwrap_or_else(|| {
            match component {
                Component::Problem => "New Problem",
                Component::Html => "New HTML",
            }
            .into()
        });

        // 1) Create a base component
        let locator = self
            .openedx_create_basic_component(&auth, &course_id, &unit_locator, &component, &name)
            .await
            .map_err(|err| err.to_string())?;

        // 2) Choose content to update with
        let final_data = if data.is_some() {
            data
        } else if component == Component::Problem && mcq_boilerplate.unwrap_or(false) {
            Some(
                r#"<problem>
                  <p>Your question here</p>
                  <multiplechoiceresponse>
                    <choicegroup type="MultipleChoice" shuffle="true">
                      <choice correct="true">Correct</choice>
                      <choice correct="false">Incorrect</choice>
                    </choicegroup>
                  </multiplechoiceresponse>
                </problem>"#
                    .to_string(),
            )
        } else {
            None
        };

        // 3) Update (if we have content and/or metadata)
        let result_value = if final_data.is_some() || metadata.is_some() {
            let updated = self
                .openedx_update_xblock_content(&auth, &course_id, &locator, final_data, metadata)
                .await
                .map_err(|err| err.to_string())?;

            match updated {
                LMSResponse::Single(v) => v,
                LMSResponse::Multiple(arr) => Value::Array(arr),
            }
        } else {
            json!({"detail": "Component created; no content/metadata to update"})
        };

        let out = json!({ "locator": locator, "result": result_value });
        Ok(out.to_string())
    }

    #[tool(
        description = "Update an XBlock (chapter/section, sequential/subsection, vertical/unit).
Provide `data` with OLX/HTML to fully control content.
The parent locator for should be in the format `block-v1:ORG+COURSE+RUN+type@course+block@course`.
Don't proceed if user is not authenticated.",
        input_schema = cached_schema_for_type::<OpenEdxUpdateXBlockPayload>()
    )]
    async fn openedx_update_xblock(
        &self,
        Parameters(OpenEdxUpdateXBlockPayload {
            auth,
            course_id,
            locator,
            data,
            metadata,
        }): Parameters<OpenEdxUpdateXBlockPayload>,
    ) -> Result<String, String> {
        if data.is_none() && metadata.is_none() {
            return Err(String::from(
                "Nothing to update: provide `data` and/or `metadata`",
            ));
        }

        self.openedx_update_xblock_content(&auth, &course_id, &locator, data, metadata)
            .await
            .map(|response| self.handle_response_single(response))
            .map_err(|err| format!("Error updating: {err}"))
    }

    #[tool(
        description = "Fetch full block graph for a course (raw) using the Course Blocks API.",
        input_schema = cached_schema_for_type::<OpenEdxCourseTreeRequest>()
    )]
    pub async fn openedx_get_course_tree_raw(
        &self,
        Parameters(OpenEdxCourseTreeRequest { auth, course_id }): Parameters<
            OpenEdxCourseTreeRequest,
        >,
    ) -> Result<String, String> {
        let client = OpenEdxClient::new(&auth.lms_url, Some(auth.access_token));

        let params = json!({
            "course_id": course_id,
            "depth": "all",
            "all_blocks": true,
            "requested_fields": "children,display_name,type,graded,student_view_url,block_id,due,start,format"
        });

        client
            .request_jwt(
                Method::GET,
                "api/courses/v1/blocks/",
                Some(to_value(params).unwrap()),
                None,
                &auth.lms_url,
            )
            .await
            .map(|response| self.handle_response_single(response))
            .map_err(|err| format!("Failed to get course tree: {err}"))
    }

    #[tool(
    description = "Read a specific block from Studio ContentStore (REQUIRES locator).\n\
    Use this if user ask to update the content of xblock specially MCQs and html.",
    input_schema = cached_schema_for_type::<OpenEdxGetBlockContentArgs>()
    )]
    pub async fn openedx_get_block_contentstore(
        &self,
        Parameters(OpenEdxGetBlockContentArgs {
            auth,
            course_id,
            locator,
        }): Parameters<OpenEdxGetBlockContentArgs>,
    ) -> Result<String, String> {
        // Hard-require a non-empty locator
        if locator.trim().is_empty() {
            return Err(LMSError::InvalidParams(
                "locator is required and cannot be empty".to_string(),
            )
            .to_string());
        }

        let client = OpenEdxClient::new(&auth.lms_url, Some(auth.access_token.clone()));

        let encoded: String = form_urlencoded::byte_serialize(locator.as_bytes()).collect();
        let endpoint = format!("api/contentstore/v0/xblock/{course_id}/{encoded}");

        client
            .request_jwt(Method::GET, &endpoint, None, None, &auth.studio_url)
            .await
            .map(|response| self.handle_response_single(response))
            .map_err(|err| format!("Fetching block from ContentStore failed: {err}"))
    }
}
