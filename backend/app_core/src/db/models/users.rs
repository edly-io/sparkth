use chrono::NaiveDateTime;
use diesel::{pg, prelude::*};
use serde::{Deserialize, Serialize};

use crate::db::{db_pool::DbPool, error::CoreError};

#[derive(Debug, Deserialize, Clone, Queryable, Selectable, Serialize, Identifiable)]
#[diesel(table_name = crate::schema::users)]
#[diesel(primary_key(id))]
#[diesel(check_for_backend(pg::Pg))]
pub struct User {
    pub id: i32,
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub is_active: bool,
    pub is_admin: bool,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

#[derive(Insertable, Serialize, Deserialize)]
#[diesel(table_name = crate::schema::users)]
pub struct NewUser {
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub is_active: bool,
    pub is_admin: bool,
}

impl User {
    pub fn insert(user: NewUser, db_pool: &DbPool) -> Result<User, CoreError> {
        use crate::schema::users::dsl::*;

        let conn = &mut db_pool.get()?;
        Ok(diesel::insert_into(users)
            .values(user)
            .returning(User::as_returning())
            .get_result(conn)?)
    }

    pub fn get(user_id: i32, db_pool: &DbPool) -> Result<User, CoreError> {
        use crate::schema::users::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(users.find(user_id).select(User::as_select()).first(conn)?)
    }

    pub fn get_by_username(user_name: &str, db_pool: &DbPool) -> Result<User, CoreError> {
        use crate::schema::users::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(users
            .filter(username.eq(user_name))
            .select(User::as_select())
            .first(conn)?)
    }

    pub fn get_by_email(user_email: &str, db_pool: &DbPool) -> Result<User, CoreError> {
        use crate::schema::users::dsl::*;

        let conn = &mut db_pool.get()?;

        Ok(users
            .filter(email.eq(user_email))
            .select(User::as_select())
            .first(conn)?)
    }

    pub fn get_list(db_pool: &DbPool) -> Result<Vec<User>, CoreError> {
        use crate::schema::users::dsl::*;

        let conn = &mut db_pool.get()?;
        let results = users.select(User::as_select()).load::<User>(conn)?;

        Ok(results)
    }

    pub fn update_password(
        user_email: &str,
        new_password_hash: String,
        db_pool: &DbPool,
    ) -> Result<(), CoreError> {
        use crate::schema::users::dsl::*;

        let conn = &mut db_pool.get()?;

        diesel::update(users.filter(email.eq(user_email)))
            .set(password_hash.eq(new_password_hash))
            .execute(conn)?;

        Ok(())
    }
}
