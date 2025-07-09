use reqwest::{Client, Method, Response};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use thiserror::Error;

/// Error type for Canvas API operations
#[derive(Error, Debug)]
pub enum CanvasError {
    #[error("Canvas API Error ({status_code}): {message}")]
    ApiError { status_code: u16, message: String },
    #[error("HTTP request failed: {0}")]
    RequestError(#[from] reqwest::Error),
    #[error("JSON parsing failed: {0}")]
    JsonError(#[from] serde_json::Error),
    #[error("Invalid HTTP method: {0}")]
    InvalidMethod(String),
}

/// Canvas API response that can be either a single object or an array
#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum CanvasResponse {
    Single(Value),
    Multiple(Vec<Value>),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Enrollment {
    pub enrollment_state: String,
    pub limit_privileges_to_course_section: bool,
    pub role: String,
    pub role_id: u64,
    #[serde(rename = "type")]
    pub enrollment_type: String,
    pub user_id: u64,
}

/// Canvas course data structure
#[derive(Debug, Serialize, Deserialize)]
pub struct Course {
    pub id: Option<u64>,
    pub name: String,
    pub course_code: Option<String>,
    pub sis_course_id: Option<String>,
    pub account_id: Option<u64>,
    pub workflow_state: Option<String>,
    pub enrollments: Vec<Enrollment>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
}

/// Canvas API client
#[derive(Debug, Clone)]
pub struct CanvasClient {
    api_url: String,
    api_token: String,
    client: Client,
}

impl CanvasClient {
    /// Create a new Canvas client
    ///
    /// # Arguments
    /// * `api_url` - The Canvas API URL (e.g., https://canvas.instructure.com/api/v1)
    /// * `api_token` - The Canvas API token
    ///
    /// # Example
    /// ```
    /// let client = CanvasClient::new(
    ///     "https://canvas.instructure.com/api/v1".to_string(),
    ///     "your-api-token".to_string()
    /// );
    /// ```
    pub fn new(api_url: String, api_token: String) -> Self {
        let client = Client::new();
        Self {
            api_url: api_url.trim_end_matches('/').to_string(),
            api_token,
            client,
        }
    }

    /// Make a request to the Canvas API
    ///
    /// # Arguments
    /// * `method` - HTTP method as string
    /// * `endpoint` - API endpoint (without base URL)
    /// * `params` - Optional query parameters
    /// * `data` - Optional request body data
    async fn request(
        &self,
        method: &str,
        endpoint: &str,
        params: Option<&HashMap<String, String>>,
        data: Option<&HashMap<String, String>>,
    ) -> Result<CanvasResponse, CanvasError> {
        let url = format!("{}/{}", self.api_url, endpoint.trim_start_matches('/'));

        eprintln!(
            "Canvas API request: url={} method={} params={:?} data={:?}",
            url, method, params, data
        );

        let http_method = match method.to_uppercase().as_str() {
            "GET" => Method::GET,
            "POST" => Method::POST,
            "PUT" => Method::PUT,
            "DELETE" => Method::DELETE,
            _ => return Err(CanvasError::InvalidMethod(method.to_string())),
        };

        let mut request = self
            .client
            .request(http_method, &url)
            .header("Authorization", format!("Bearer {}", self.api_token));

        if let Some(params) = params {
            request = request.query(params);
        }

        if let Some(data) = data {
            request = request.form(data);
        }

        let response = request.send().await?;

        if !response.status().is_success() {
            return Err(self.handle_error_response(response).await?);
        }

        let response_text = response.text().await?;

        if response_text.is_empty() {
            return Ok(CanvasResponse::Single(
                Value::Object(serde_json::Map::new()),
            ));
        }

        let json_value: Value = serde_json::from_str(&response_text)?;

        match json_value {
            Value::Array(arr) => Ok(CanvasResponse::Multiple(arr)),
            single => Ok(CanvasResponse::Single(single)),
        }
    }

    /// Handle error responses from the Canvas API
    async fn handle_error_response(&self, response: Response) -> Result<CanvasError, CanvasError> {
        let status_code = response.status().as_u16();
        let error_text = response.text().await?;

        let error_message = if let Ok(error_json) = serde_json::from_str::<Value>(&error_text) {
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

        Ok(CanvasError::ApiError {
            status_code,
            message: error_message,
        })
    }

    /// Get all courses
    ///
    /// # Arguments
    /// * `params` - Optional query parameters
    ///
    /// # Returns
    /// Vector of course data as JSON values
    pub async fn get_courses(
        &self,
        params: Option<&HashMap<String, String>>,
    ) -> Result<Vec<Value>, CanvasError> {
        match self.request("GET", "courses", params, None).await? {
            CanvasResponse::Multiple(courses) => Ok(courses),
            CanvasResponse::Single(course) => Ok(vec![course]),
        }
    }

    /// Get a specific course by ID
    ///
    /// # Arguments
    /// * `course_id` - The course ID
    ///
    /// # Returns
    /// Course data as JSON value
    pub async fn get_course(&self, course_id: &str) -> Result<Value, CanvasError> {
        match self
            .request("GET", &format!("courses/{}", course_id), None, None)
            .await?
        {
            CanvasResponse::Single(course) => Ok(course),
            CanvasResponse::Multiple(mut courses) => Ok(courses.pop().unwrap_or(Value::Null)),
        }
    }

    /// Create a new course
    ///
    /// # Arguments
    /// * `account_id` - The account ID where the course will be created
    /// * `name` - The course name
    /// * `course_code` - Optional course code
    /// * `sis_course_id` - Optional SIS course ID
    ///
    /// # Returns
    /// Created course data as JSON value
    pub async fn create_course(
        &self,
        account_id: String,
        name: String,
        course_code: Option<String>,
        sis_course_id: Option<String>,
    ) -> Result<Value, CanvasError> {
        let mut data = HashMap::new();
        data.insert("course[name]".to_string(), name.to_string());

        if let Some(code) = course_code {
            data.insert("course[course_code]".to_string(), code.to_string());
        }

        if let Some(sis_id) = sis_course_id {
            data.insert("course[sis_course_id]".to_string(), sis_id.to_string());
        }

        match self
            .request(
                "POST",
                &format!("accounts/{}/courses", account_id),
                None,
                Some(&data),
            )
            .await?
        {
            CanvasResponse::Single(course) => Ok(course),
            CanvasResponse::Multiple(mut courses) => Ok(courses.pop().unwrap_or(Value::Null)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_canvas_client_creation() {
        let client = CanvasClient::new(
            "https://canvas.instructure.com/api/v1".to_string(),
            "test-token".to_string(),
        );

        assert_eq!(client.api_url, "https://canvas.instructure.com/api/v1");
        assert_eq!(client.api_token, "test-token");
    }

    #[test]
    fn test_api_url_trimming() {
        let client = CanvasClient::new(
            "https://canvas.instructure.com/api/v1/".to_string(),
            "test-token".to_string(),
        );

        assert_eq!(client.api_url, "https://canvas.instructure.com/api/v1");
    }
}
