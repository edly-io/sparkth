use reqwest::{
    Client, Method, Response,
    header::{ACCEPT, AUTHORIZATION, CONTENT_TYPE},
};
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
        .header(AUTHORIZATION, format!("{auth:?} {token}"))
        .header(ACCEPT, "application/json")
        .header(CONTENT_TYPE, "application/json");

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

pub async fn handle_error_response(response: Response) -> LMSError {
    let status_code = response.status().as_u16();
    let error_text = response.text().await.unwrap_or_default();

    let message = from_str::<Value>(&error_text)
        .ok()
        .and_then(|v| v.get("message")?.as_str().map(|s| s.to_string()))
        .unwrap_or(error_text);

    LMSError::Api {
        status_code,
        message,
    }
}
