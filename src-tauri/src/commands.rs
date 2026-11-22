use crate::core::subtitles::{generate_subtitles, SubtitleConfig, SubtitleSegment};
use crate::core::translation::{TranslationConfig, Translator};
use crate::core::types::*;
use crate::db;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Command;
use uuid::Uuid;

/// Запрос генерации субтитров (приходит из фронтенда).
#[derive(Debug, Serialize, Deserialize)]
pub struct GenerateSubtitlesRequest {
    pub video_path: String,
    pub model_path: String,
    pub language: String,
    pub translate_to_en: bool,
}

/// Результат генерации субтитров.
#[derive(Debug, Serialize, Deserialize)]
pub struct GenerateSubtitlesResponse {
    pub segments: Vec<SubtitleSegment>,
    pub output_path: String,
}

/// Запрос перевода субтитров.
#[derive(Debug, Serialize, Deserialize)]
pub struct TranslateSubtitlesRequest {
    pub segments: Vec<SubtitleSegment>,
    pub api_url: String,
    pub api_key: Option<String>,
    pub source_lang: String,
    pub target_lang: String,
}

/// Запрос синтеза речи (TTS) для дублирования.
#[derive(Debug, Serialize, Deserialize)]
pub struct TtsSynthesizeRequest {
    pub segments: Vec<SubtitleSegment>,
    pub api_url: String,
    pub api_key: Option<String>,
    pub voice: String,
    pub model: String,
    pub output_dir: String,
}

/// Ответ синтеза речи.
#[derive(Debug, Serialize, Deserialize)]
pub struct TtsSynthesizeResponse {
    pub combined_audio: String,
    pub segments_count: usize,
}

#[tauri::command]
pub fn init_app(db_path: String) -> Result<(), String> {
    crate::init_db_path(db_path);
    Ok(())
}

#[tauri::command]
pub fn select_video() -> Result<Option<String>, String> {
    let path = rfd::FileDialog::new()
        .add_filter("Видео", &["mp4", "mov", "mkv", "avi"])
        .set_title("Выберите видео")
        .pick_file()
        .map(|p| p.to_string_lossy().to_string());
    Ok(path)
}

#[tauri::command]
pub fn read_file_bytes(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| e.to_string())
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
pub fn create_project_cmd(
    name: String,
    source_path: String,
    preset: String,
) -> Result<db::Project, String> {
    db::create_project(&name, &source_path, &preset).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn list_projects_cmd() -> Result<Vec<db::Project>, String> {
    db::list_projects().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn save_clips_cmd(project_id: String, clips: Vec<ClipSegment>) -> Result<(), String> {
    for clip in clips {
        let c = ClipSegment {
            project_id: Some(project_id.clone()),
            ..clip
        };
        db::save_clip(&c).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn list_clips_cmd(project_id: String) -> Result<Vec<db::ClipSegment>, String> {
    db::list_clips(&project_id).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn render_clips_cmd(
    project_id: String,
    source: String,
    clips: Vec<ClipSegment>,
    settings: RenderSettings,
    subtitle_segments: Option<Vec<SubtitleSegment>>,
    dub_audio_path: Option<String>,
) -> Result<String, String> {
    let job = db::create_render_job(&project_id).map_err(|e| e.to_string())?;
    let job_id = job.id.clone();

    // Рендер в фоне на рантайме Tauri (не создаём свой tokio::Runtime)
    let job_id_for_task = job_id.clone();
    tauri::async_runtime::spawn(async move {
        let total = clips.len() as f64;
        let mut done = 0.0;
        let mut outputs: Vec<String> = Vec::new();
        let subs = subtitle_segments.as_deref().unwrap_or(&[]);

        for clip in &clips {
            let preset = crate::core::types::PRESETS
                .iter()
                .find(|p| p.name == settings.preset)
                .unwrap_or(&crate::core::types::PRESETS[1]);
            let out = format!("rendered_{}.mp4", Uuid::new_v4());
            match crate::core::render::render_single_clip(
                &source,
                clip,
                preset,
                &settings,
                &out,
                subs,
                dub_audio_path.as_deref(),
            ) {
                Ok(_) => {
                    outputs.push(out.clone());
                    let mut c = clip.clone();
                    c.output_path = Some(out.clone());
                    let _ = db::save_clip(&c);
                    done += 1.0;
                    let prog = done / total * 100.0;
                    let _ = db::update_render_job(
                        &job_id_for_task,
                        "rendering",
                        prog,
                        Some(&out),
                        None,
                    );
                }
                Err(e) => {
                    let _ = db::update_render_job(
                        &job_id_for_task,
                        "error",
                        done / total * 100.0,
                        None,
                        Some(&e.to_string()),
                    );
                    break;
                }
            }
        }

        let status = if outputs.len() == clips.len() {
            "done"
        } else {
            "error"
        };
        let _ = db::update_render_job(
            &job_id_for_task,
            status,
            100.0,
            outputs.last().map(|s| s.as_str()),
            None,
        );
    });

    Ok(job_id)
}

#[tauri::command]
pub fn list_render_jobs_cmd(project_id: String) -> Result<Vec<db::RenderJob>, String> {
    db::list_render_jobs(&project_id).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn generate_subtitles_cmd(
    req: GenerateSubtitlesRequest,
) -> Result<GenerateSubtitlesResponse, String> {
    let config = SubtitleConfig {
        model_path: req.model_path,
        language: req.language,
        translate_to_en: req.translate_to_en,
        output_format: "srt".to_string(),
    };
    let result = generate_subtitles(&req.video_path, &config).map_err(|e| e.to_string())?;
    Ok(GenerateSubtitlesResponse {
        segments: result.segments,
        output_path: result.output_path.to_string_lossy().to_string(),
    })
}

#[tauri::command]
pub fn translate_subtitles_cmd(
    req: TranslateSubtitlesRequest,
) -> Result<Vec<SubtitleSegment>, String> {
    let config = TranslationConfig {
        api_url: req.api_url,
        api_key: req.api_key,
        source_lang: req.source_lang,
        target_lang: req.target_lang,
    };
    let translator = Translator::new(config);
    translator
        .translate_segments(&req.segments)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_synthesize_cmd(req: TtsSynthesizeRequest) -> Result<TtsSynthesizeResponse, String> {
    let config = crate::core::tts::TtsConfig {
        api_url: req.api_url,
        api_key: req.api_key,
        voice: req.voice,
        model: req.model,
        output_dir: PathBuf::from(&req.output_dir),
    };
    let client = crate::core::tts::TtsClient::new(config);

    let mut tts_segments = Vec::new();
    for (i, seg) in req.segments.iter().enumerate() {
        let audio_path = client
            .synthesize_segment(seg, i)
            .map_err(|e| e.to_string())?;
        tts_segments.push(crate::core::tts::TtsAudioSegment {
            start: seg.start,
            end: seg.end,
            text: seg.text.clone(),
            audio_path,
        });
    }

    let clip_duration = req
        .segments
        .iter()
        .map(|s| s.end - s.start)
        .fold(0.0f64, f64::max);
    let combined = client
        .combine_audio(&tts_segments, clip_duration)
        .map_err(|e| e.to_string())?;

    Ok(TtsSynthesizeResponse {
        combined_audio: combined.to_string_lossy().to_string(),
        segments_count: tts_segments.len(),
    })
}

#[tauri::command]
pub fn open_output_folder(path: String) -> Result<(), String> {
    // Открываем папку в проводнике Windows. Если передан путь к файлу — открываем его родительскую папку.
    let target = PathBuf::from(&path);
    let folder = if target.is_file() {
        target
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .to_path_buf()
    } else {
        target
    };

    Command::new("explorer")
        .arg(&folder)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("не удалось открыть папку: {e}"))
}
