use crate::{CoreError, User, get_db_pool};
use once_cell::sync::Lazy;
use regex::Regex;

static EMAIL_REGEX: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$").unwrap());

pub fn validate_email(email: &str) -> Result<(), CoreError> {
    if !EMAIL_REGEX.is_match(email) {
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
