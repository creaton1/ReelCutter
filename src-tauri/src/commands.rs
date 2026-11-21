use crate::core::types::*;
use crate::db;
use anyhow::Result;
use uuid::Uuid;

#[tauri::command]
pub fn init_app(db_path: String) -> Result<(), String> {
    crate::init_db_path(db_path);
    Ok(())
}

#[tauri::command]
pub fn select_video() -> Result<Option<String>, String> {
    Ok(None)
}

#[tauri::command]
pub fn probe_video(path: String) -> Result<VideoInfo, String> {
    crate::core::probe_video(&path).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn detect_highlights(path: String, preset: String) -> Result<Vec<Highlight>, String> {
    let max_dur = crate::core::types::PRESETS
        .iter()
        .find(|p| p.name == preset)
        .map(|p| p.max_duration)
        .unwrap_or(60.0);
    crate::core::detect_highlights(&path, max_dur).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn create_project_cmd(name: String, source_path: String, preset: String) -> Result<db::Project, String> {
    db::create_project(&name, &source_path, &preset).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn list_projects_cmd() -> Result<Vec<db::Project>, String> {
    db::list_projects().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn save_clips_cmd(project_id: String, clips: Vec<ClipSegment>) -> Result<(), String> {
    for clip in clips {
        let mut c = clip;
        c.project_id = Some(project_id.clone());
        db::save_clip(&c).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn list_clips_cmd(project_id: String) -> Result<Vec<db::ClipSegment>, String> {
    db::list_clips(&project_id).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn render_clips_cmd(
    project_id: String,
    source: String,
    clips: Vec<ClipSegment>,
    settings: RenderSettings,
) -> Result<String, String> {
    let job = db::create_render_job(&project_id).map_err(|e| e.to_string())?;
    let job_id = job.id.clone();

    // Запускаем рендер в фоне (tokio)
    let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
    let job_id_for_task = job_id.clone();
    rt.spawn(async move {
        let total = clips.len() as f64;
        let mut done = 0.0;
        let mut outputs: Vec<String> = Vec::new();

        for clip in &clips {
            let out = format!("rendered_{}.mp4", Uuid::new_v4());
            match crate::core::render_single_clip(&source, clip, &crate::core::types::PRESETS[1], &settings, &out) {
                Ok(_) => {
                    outputs.push(out.clone());
                    let mut c = clip.clone();
                    c.output_path = Some(out.clone());
                    let _ = db::save_clip(&c);
                    done += 1.0;
                    let prog = done / total * 100.0;
                    let _ = db::update_render_job(&job_id_for_task, "rendering", prog, Some(&out), None);
                }
                Err(e) => {
                    let _ = db::update_render_job(&job_id_for_task, "error", done / total * 100.0, None, Some(&e.to_string()));
                    break;
                }
            }
        }

        let status = if outputs.len() == clips.len() { "done" } else { "error" };
        let _ = db::update_render_job(&job_id_for_task, status, 100.0, outputs.last().map(|s| s.as_str()), None);
    });

    Ok(job_id)
}

#[tauri::command]
pub fn list_render_jobs_cmd(project_id: String) -> Result<Vec<db::RenderJob>, String> {
    db::list_render_jobs(&project_id).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn open_output_folder(_path: String) -> Result<(), String> {
    Ok(())
}
