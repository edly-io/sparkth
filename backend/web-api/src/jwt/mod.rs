use app_core::User;
use chrono::{Duration, Utc};
use jsonwebtoken::{Algorithm, DecodingKey, EncodingKey, Header, Validation, decode, encode};
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub const JWT_DEFAULT_EXPIRATION_HOURS: i64 = 24;
pub const JWT_DEFAULT_REFRESH_EXPIRATION_DAYS: i64 = 7;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct JWTClaims {
    pub sub: String,
    pub username: String,
    pub email: String,
    pub role: String,
    pub exp: usize,
    pub iat: usize,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct JWTRefreshClaims {
    pub sub: String,
    pub token_id: String,
    pub exp: usize,
    pub iat: usize,
}

#[derive(Debug, Error)]
pub enum JWTError {
    #[error("Invalid token")]
    InvalidToken,
    #[error("Token expired")]
    ExpiredToken,
    #[error("Invalid signature")]
    InvalidSignature,
    #[error("Missing secret")]
    MissingSecret,
    #[error("Encoding failed: {0}")]
    EncodingFailed(String),
}

#[derive(Clone)]
pub struct JWTService {
    encoding_key: EncodingKey,
    decoding_key: DecodingKey,
    expiration_hours: i64,
    refresh_expiration_days: i64,
}

impl JWTService {
    pub fn new(
        secret: &str,
        expiration_hours: Option<i64>,
        refresh_expiration_days: Option<i64>,
    ) -> Result<Self, JWTError> {
        if secret.is_empty() {
            return Err(JWTError::MissingSecret);
        }

        Ok(JWTService {
            encoding_key: EncodingKey::from_secret(secret.as_ref()),
            decoding_key: DecodingKey::from_secret(secret.as_ref()),
            expiration_hours: expiration_hours.unwrap_or(JWT_DEFAULT_EXPIRATION_HOURS),
            refresh_expiration_days: refresh_expiration_days
                .unwrap_or(JWT_DEFAULT_REFRESH_EXPIRATION_DAYS),
        })
    }

    pub fn encode_access_token(&self, user: &User) -> Result<String, JWTError> {
        let now = Utc::now();
        let expire = now + Duration::hours(self.expiration_hours);

        let claims = JWTClaims {
            sub: user.id.to_string(),
            username: user.username.clone(),
            email: user.email.clone(),
            role: if user.is_admin {
                "admin".to_string()
            } else {
                "user".to_string()
            },
            exp: expire.timestamp() as usize,
            iat: now.timestamp() as usize,
        };

        encode(&Header::default(), &claims, &self.encoding_key)
            .map_err(|e| JWTError::EncodingFailed(e.to_string()))
    }

    pub fn encode_refresh_token(&self, user_id: &str) -> Result<String, JWTError> {
        let now = Utc::now();
        let expire = now + Duration::days(self.refresh_expiration_days);

        let claims = JWTRefreshClaims {
            sub: user_id.to_string(),
            token_id: uuid::Uuid::new_v4().to_string(),
            exp: expire.timestamp() as usize,
            iat: now.timestamp() as usize,
        };

        encode(&Header::default(), &claims, &self.encoding_key)
            .map_err(|e| JWTError::EncodingFailed(e.to_string()))
    }

    pub fn decode_refresh_token(&self, token: &str) -> Result<JWTRefreshClaims, JWTError> {
        let validation = Validation::new(Algorithm::HS256);
        let token_data = decode::<JWTRefreshClaims>(token, &self.decoding_key, &validation)
            .map_err(|e| match e.kind() {
                jsonwebtoken::errors::ErrorKind::ExpiredSignature => JWTError::ExpiredToken,
                jsonwebtoken::errors::ErrorKind::InvalidSignature => JWTError::InvalidSignature,
                _ => JWTError::InvalidToken,
            })?;

        Ok(token_data.claims)
    }

    pub fn get_expiration_hours(&self) -> i64 {
        self.expiration_hours
    }
}
