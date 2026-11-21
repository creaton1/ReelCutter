pub mod commands;
pub mod core;
pub mod db;

use std::sync::OnceLock;

pub static DB_PATH: OnceLock<String> = OnceLock::new();

pub fn init_db_path(path: String) {
    let _ = DB_PATH.set(path);
}

pub fn get_db_path() -> Option<&'static str> {
    DB_PATH.get().map(|s| s.as_str())
}
