use std::io::{self, Write};

use app_core::{User, get_db_pool, validate_email, validate_confirm_password};
use bcrypt::{DEFAULT_COST, hash};
use tracing::{error, info};
use tracing_subscriber::EnvFilter;
use dotenvy::dotenv;

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

    let email = loop {
        print!("1. Enter your email address: ");
        io::stdout().flush()?;
        let mut email_input = String::new();
        io::stdin().read_line(&mut email_input)?;
        let email = email_input.trim().to_string();

        // Validate email using the utility function
        match validate_email(&email) {
            Ok(_) => {
                break email;
            }
            Err(_) => {
                error!("Invalid email format or email already exists. Please enter a valid, unique email address.");
                continue;
            }
        }
    };

    let password = loop {
        let password = rpassword::prompt_password("2. Enter your new password: ")?;

        let password_confirmation = rpassword::prompt_password("3. Confirm your new password: ")?;

        match validate_confirm_password(&password, &password_confirmation) {
            Ok(()) => {}
            Err(e) => {
                error!("Password validation error: {}", e);
                continue;
            }
        }

        break password;
    };

    let password_hash = hash(password, DEFAULT_COST)?;

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
