use crate::{CoreError, User, get_db_pool};
use regex::Regex;

pub fn validate_email(email: &str) -> Result<(), CoreError> {
    let email_regex = Regex::new(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$").unwrap();
    if !email_regex.is_match(email) {
        return Err(CoreError::Database(
            diesel::result::Error::RollbackTransaction,
        ));
    }

    Ok(())
}

pub fn check_user_exists(email: &str) -> bool {
    let db_pool = get_db_pool();
    match User::get_by_email(email, db_pool) {
        Ok(_) => true,
        Err(CoreError::NotFound(_)) => false,
        Err(_) => false, // Consider other errors as user doesn't exist for now
    }
}

pub fn validate_confirm_password(
    password: &str,
    password_confirmation: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    if password != password_confirmation {
        return Err("Passwords do not match".into());
    }

    if password.len() < 8 {
        return Err("Password must be at least 8 characters long".into());
    }

    Ok(())
}
