use std::io::{self, BufRead, Write};

use app_core::utils::{check_user_exists, validate_confirm_password, validate_email};
use app_core::{NewUser, User, get_db_pool};
use bcrypt::{DEFAULT_COST, hash};
use dotenvy::dotenv;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load environment variables from .env file
    dotenv().ok();
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    info!("👋  Welcome to Sparkth!");
    info!("Let's create your first user account.");

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
                if check_user_exists(&email) {
                    error!("Email already exists. Please enter a different email address.");
                    continue;
                }
                break email;
            }
            Err(_) => {
                error!(
                    "Invalid email format or email already exists. Please enter a valid, unique email address."
                );
                continue;
            }
        }
    };

    let password = loop {
        let password = rpassword::prompt_password("2. Enter your password: ")?;

        let password_confirmation = rpassword::prompt_password("3. Confirm your password: ")?;

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

    let new_user = NewUser {
        username: email.clone(),
        email: email.clone(),
        password_hash,
        first_name: None,
        last_name: None,
        is_active: true,
        is_admin: false,
    };

    match User::insert(new_user, db_pool) {
        Ok(user) => {
            info!("✅ Account created successfully!");
            info!("User ID: {}", user.id);
            info!("Email: {}", user.email);
        }
        Err(e) => {
            error!("Error creating user: {e}");
            return Err(Box::new(e));
        }
    }

    Ok(())
}
