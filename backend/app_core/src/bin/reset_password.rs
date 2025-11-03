use app_core::{
    User, get_db_pool,
    utils::{check_user_exists, validate_email},
};

use argon2::{
    Argon2,
    password_hash::{PasswordHasher, SaltString, rand_core::OsRng},
};

use dotenvy::dotenv;
use inquire::{Password, Text, validator::Validation};
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load environment variables from .env file
    dotenv().ok();
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    info!("🔑 Welcome to Sparkth Password Reset!");
    info!("Let's reset your password.");

    let db_pool = get_db_pool();

    let email = Text::new("1. Enter your email address:")
        .with_validator(|input: &str| {
            if let Err(_) = validate_email(input) {
                return Ok(Validation::Invalid(
                    "Invalid email format. Please enter a valid email address.".into(),
                ));
            }

            if !check_user_exists(input) {
                return Ok(Validation::Invalid(
                    format!(
                        "User {} doesn't exist. Please enter a different email address.",
                        input
                    )
                    .into(),
                ));
            }

            Ok(Validation::Valid)
        })
        .prompt()?;

    let password = Password::new("2. Enter your password: ")
        .with_display_mode(inquire::PasswordDisplayMode::Hidden)
        .prompt()?;

    let salt = SaltString::generate(&mut OsRng);
    let argon2 = Argon2::default();

    let password_hash = argon2
        .hash_password(password.as_bytes(), &salt)
        .map_err(|e| format!("hashing failed: {:?}", e))?
        .to_string();

    match User::update_password(&email, password_hash, db_pool) {
        Ok(_) => {
            info!("✅ Password reset successfully!");
            info!("Your password has been updated for: {}", email);
        }
        Err(e) => {
            error!("Error resetting password: {e}");
            return Err(Box::new(e));
        }
    }

    Ok(())
}
