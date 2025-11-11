use axum::{
    body::Body,
    extract::State,
    http::{Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use jsonwebtoken::{Algorithm, DecodingKey, Validation, decode};
use log::warn;

use crate::jwt::JWTClaims;

pub async fn inject_jwt_user(
    State(secret): State<String>,
    mut request: Request<Body>,
    next: Next,
) -> Response {
    let token_opt = request
        .headers()
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|h| h.to_str().ok())
        .and_then(|s| s.strip_prefix("Bearer "))
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(String::from);

    if let Some(token) = token_opt {
        let decoding_key = DecodingKey::from_secret(secret.as_bytes());
        let validation = Validation::new(Algorithm::HS256);

        if let Ok(data) = decode::<JWTClaims>(&token, &decoding_key, &validation) {
            request.extensions_mut().insert(data.claims);
        } else {
            warn!("Invalid or expired JWT");
            return (StatusCode::UNAUTHORIZED, "Invalid or expired token").into_response();
        }
    } else {
        warn!("Missing Authorization header");
        return (StatusCode::UNAUTHORIZED, "Missing Authorization header").into_response();
    }

    next.run(request).await
}
