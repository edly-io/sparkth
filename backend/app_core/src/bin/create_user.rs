use std::io::{self, Write};

use app_core::{NewUser, User, get_db_pool};
use bcrypt::{DEFAULT_COST, hash};
use regex::Regex;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("👋  Welcome to Sparkth!");
    println!("Let's create your first user account.");

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
                eprintln!("Error: A user with this email already exists. Please try again.");
                continue;
            }
            Err(_) => {
                break email;
            }
        }
    };

    let password = loop {
        let password = rpassword::prompt_password("2. Enter your password: ")?;

        let password_confirmation = rpassword::prompt_password("3. Confirm your password: ")?;

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
            println!("✅ Account created successfully!");
            println!("User ID: {}", user.id);
            println!("Email: {}", user.email);
        }
        Err(e) => {
            eprintln!("Error creating user: {e}");
            return Err(Box::new(e));
        }
    }

    Ok(())
}
