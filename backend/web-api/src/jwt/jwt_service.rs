use std::env;

use crate::jwt::JWTService;

pub fn init_jwt_service(secret: &str) -> JWTService {
    let jwt_expiration_hours = env::var("JWT_EXPIRATION_HOURS")
        .ok()
        .and_then(|s| s.parse().ok());
    let jwt_refresh_expiration_days = env::var("JWT_REFRESH_EXPIRATION_DAYS")
        .ok()
        .and_then(|s| s.parse().ok());

    JWTService::new(secret, jwt_expiration_hours, jwt_refresh_expiration_days)
        .expect("Failed to create JWT service")
}
