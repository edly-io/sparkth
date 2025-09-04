use reqwest::{Client, Method, Response, header::{AUTHORIZATION, ACCEPT}};
use serde::Deserialize;
use serde_json::{Value, from_str};
use url::Url;

use crate::plugins::{errors::LMSError, response::LMSResponse};

#[derive(Debug, Deserialize)]
pub enum Auth {
    Jwt,
    Bearer,
}

pub async fn request(
    auth: Auth,
    token: &str,
    http_method: Method,
    url: Url,
    params: Option<Value>,
    payload: Option<Value>,
    client: &Client,
) -> Result<LMSResponse, LMSError> {
    let mut request = client
        .request(http_method, url)
        .header(AUTHORIZATION, format!("{:?} {token}", auth))
        .header(ACCEPT, "application/json")
        .header("CONTENT_TYPE", "application/json");

    if let Some(params) = params {
        request = request.query(&params);
    }

    if let Some(payload) = payload {
        request = request.json(&payload);
    }

    let response = request.send().await?;

    if !response.status().is_success() {
        return Err(handle_error_response(response).await);
    }

    let response_text = response.text().await?;

    if response_text.is_empty() {
        return Ok(LMSResponse::Single(Value::Object(serde_json::Map::new())));
    }

    let json_value: Value = from_str(&response_text)?;

    match json_value {
        Value::Array(arr) => Ok(LMSResponse::Multiple(arr)),
        single => Ok(LMSResponse::Single(single)),
    }
}

async fn handle_error_response(response: Response) -> LMSError {
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

    LMSError::Api {
        status_code,
        message: error_message,
    }
}
