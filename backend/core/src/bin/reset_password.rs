use std::io::{self, Write};

use bcrypt::{DEFAULT_COST, hash};
use regex::Regex;

use core::db::db_pool::get_db_pool;
use core::db::models::users::User;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔑 Welcome to Sparkth Password Reset!");
    println!("Let's reset your password.");

    let db_pool = get_db_pool();

    // Email regex pattern for basic validation
    let email_regex = Regex::new(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")?;

    let email = loop {
        print!("1. Enter your email address: ");
        io::stdout().flush()?;
        let mut email_input = String::new();
        io::stdin().read_line(&mut email_input)?;
        let email = email_input.trim().to_string();

        // Validate email format
        if !email_regex.is_match(&email) {
            eprintln!(
                "Error: Invalid email format. Please enter a valid email address (example: user@domain.com)."
            );
            continue;
        }

        match User::get_by_email(&email, db_pool) {
            Ok(_) => {
                break email;
            }
            Err(_) => {
                eprintln!("Error: No user found with this email. Please try again.");
                continue;
            }
        }
    };

    let password = loop {
        let password = rpassword::prompt_password("2. Enter your new password: ")?;

        let password_confirmation = rpassword::prompt_password("3. Confirm your new password: ")?;

        if password != password_confirmation {
            eprintln!("Error: Passwords do not match. Please try again.");
            continue;
        }

        // Validate password length
        if password.len() < 8 {
            eprintln!("Error: Password must be at least 8 characters long. Please try again.");
            continue;
        }

        break password;
    };

    let password_hash = hash(password, DEFAULT_COST)?;

    match User::update_password(&email, password_hash, db_pool) {
        Ok(_) => {
            println!("✅ Password reset successfully!");
            println!("Your password has been updated for: {}", email);
        }
        Err(e) => {
            eprintln!("Error resetting password: {e}");
            return Err(Box::new(e));
        }
    }

    Ok(())
}
