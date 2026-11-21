pub use crate::core::types::ClipSegment;
use crate::get_db_path;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub source_path: String,
    pub preset: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenderJob {
    pub id: String,
    pub project_id: String,
    pub status: String, // pending, rendering, done, error
    pub progress: f64,
    pub output_path: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Default, Serialize, Deserialize)]
pub struct DbState {
    pub projects: Vec<Project>,
    pub clips: Vec<ClipSegment>,
    pub render_jobs: Vec<RenderJob>,
}

fn db_file_path() -> Result<PathBuf, Box<dyn std::error::Error>> {
    let path = get_db_path()
        .ok_or_else(|| "db path not set".to_string())?;
    let p = PathBuf::from(path);
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent)?;
    }
    Ok(p)
}

fn load_state() -> Result<DbState, Box<dyn std::error::Error>> {
    let path = db_file_path()?;
    if !path.exists() {
        return Ok(DbState::default());
    }
    let content = fs::read_to_string(&path)?;
    if content.trim().is_empty() {
        return Ok(DbState::default());
    }
    let state: DbState = serde_json::from_str(&content)?;
    Ok(state)
}

fn save_state(state: &DbState) -> Result<(), Box<dyn std::error::Error>> {
    let path = db_file_path()?;
    let json = serde_json::to_string_pretty(state)?;
    fs::write(&path, json)?;
    Ok(())
}

pub fn create_project(name: &str, source_path: &str, preset: &str) -> Result<Project, Box<dyn std::error::Error>> {
    let mut state = load_state()?;
    let id = Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();
    let project = Project {
        id: id.clone(),
        name: name.to_string(),
        source_path: source_path.to_string(),
        preset: preset.to_string(),
        created_at: now.clone(),
        updated_at: now,
    };
    state.projects.push(project.clone());
    save_state(&state)?;
    Ok(project)
}

pub fn list_projects() -> Result<Vec<Project>, Box<dyn std::error::Error>> {
    let state = load_state()?;
    let mut projects = state.projects;
    projects.sort_by(|a, b| b.updated_at.cmp(&a.updated_at));
    Ok(projects)
}

pub fn save_clip(clip: &ClipSegment) -> Result<(), Box<dyn std::error::Error>> {
    let mut state = load_state()?;
    state.clips.retain(|c| c.id != clip.id);
    state.clips.push(clip.clone());
    save_state(&state)?;
    Ok(())
}

pub fn list_clips(project_id: &str) -> Result<Vec<ClipSegment>, Box<dyn std::error::Error>> {
    let state = load_state()?;
    let mut clips: Vec<ClipSegment> = state
        .clips
        .iter()
        .filter(|c| c.project_id.as_deref() == Some(project_id))
        .cloned()
        .collect();
    clips.sort_by(|a, b| a.start.partial_cmp(&b.start).unwrap_or(std::cmp::Ordering::Equal));
    Ok(clips)
}

pub fn create_render_job(project_id: &str) -> Result<RenderJob, Box<dyn std::error::Error>> {
    let mut state = load_state()?;
    let id = Uuid::new_v4().to_string();
    let job = RenderJob {
        id: id.clone(),
        project_id: project_id.to_string(),
        status: "pending".to_string(),
        progress: 0.0,
        output_path: None,
        error: None,
    };
    state.render_jobs.push(job.clone());
    save_state(&state)?;
    Ok(job)
}

pub fn update_render_job(
    id: &str,
    status: &str,
    progress: f64,
    output_path: Option<&str>,
    error: Option<&str>,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut state = load_state()?;
    if let Some(job) = state.render_jobs.iter_mut().find(|j| j.id == id) {
        job.status = status.to_string();
        job.progress = progress;
        job.output_path = output_path.map(|s| s.to_string());
        job.error = error.map(|s| s.to_string());
    }
    save_state(&state)?;
    Ok(())
}

pub fn list_render_jobs(project_id: &str) -> Result<Vec<RenderJob>, Box<dyn std::error::Error>> {
    let state = load_state()?;
    let mut jobs: Vec<RenderJob> = state
        .render_jobs
        .iter()
        .filter(|j| j.project_id == project_id)
        .cloned()
        .collect();
    jobs.sort_by(|a, b| b.id.cmp(&a.id));
    Ok(jobs)
}
