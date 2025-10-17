use diesel::{
    PgConnection,
    r2d2::{ConnectionManager, Pool},
};
use dotenvy::dotenv;
use std::{env, sync::OnceLock};

pub type DbPool = Pool<ConnectionManager<PgConnection>>;

fn establish_pooled_connection() -> Pool<ConnectionManager<PgConnection>> {
    dotenv().ok();
    let database_url = env::var("DATABASE_URL").expect("DATABASE_URL must be set");
    let manager = ConnectionManager::<PgConnection>::new(database_url);
    Pool::builder()
        .build(manager)
        .expect("Failed to create database pool.")
}

static POOL: OnceLock<DbPool> = OnceLock::new();

pub fn get_db_pool() -> &'static DbPool {
    POOL.get_or_init(establish_pooled_connection)
}
