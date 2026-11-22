#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use reelcutter_core::commands;
use tauri::WindowBuilder;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::init_app,
            commands::select_video,
            commands::probe_video,
            commands::detect_highlights,
            commands::generate_subtitles_cmd,
            commands::translate_subtitles_cmd,
            commands::tts_synthesize_cmd,
            commands::create_project_cmd,
            commands::list_projects_cmd,
            commands::save_clips_cmd,
            commands::list_clips_cmd,
            commands::render_clips_cmd,
            commands::list_render_jobs_cmd,
            commands::open_output_folder,
            commands::read_file_bytes,
        ])
        .setup(|app| {
            WindowBuilder::new(app, "main")
                .title("ReelCutter")
                .inner_size(1200.0, 800.0)
                .resizable(true)
                .center()
                .build()?;

            // Используем относительный путь к БД; в продакшене — через tauri::path resolver
            let db_path = std::env::current_dir()
                .unwrap_or_else(|_| std::path::PathBuf::from("."))
                .join("reelcutter.db")
                .to_string_lossy()
                .to_string();
            let _ = commands::init_app(db_path);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("ошибка запуска Tauri");
}
