use argon2::{Argon2, PasswordHash, PasswordVerifier};

use crate::{CoreError, User, get_db_pool};

#[derive(Clone)]
pub struct UserService;

impl UserService {
    pub fn get_user(&self, user_id: i32) -> Result<User, CoreError> {
        let db_pool = get_db_pool();
        User::get(user_id, db_pool)
    }

    pub fn get_users(&self) -> Result<Vec<User>, CoreError> {
        let db_pool = get_db_pool();
        User::get_list(db_pool)
    }

    pub fn authenticate(&self, email: String, password: String) -> Result<User, CoreError> {
        let db_pool = get_db_pool();
        let user = User::get_by_email(&email, db_pool)?;

        let stored_hash = &user.password_hash;

        let parsed_hash = PasswordHash::new(stored_hash)
            .map_err(|_| CoreError::AuthError("Invalid stored password hash".into()))?;

        let argon2 = Argon2::default();

        if argon2
            .verify_password(password.as_bytes(), &parsed_hash)
            .is_ok()
        {
            Ok(user)
        } else {
            Err(CoreError::AuthError("Invalid email or password".into()))
        }
    }
}
