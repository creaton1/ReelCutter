pub mod analyzer;
pub mod detect;
pub mod ffmpeg;
pub mod render;
pub mod types;

use crate::core::render::render_single_clip;
use crate::core::types::*;
use anyhow::{Context, Result};
use rayon::prelude::*;

/// Анализирует видеофайл и возвращает информацию о нём (длительность, размер, FPS, аудио).
pub fn probe_video(path: &str) -> Result<VideoInfo> {
    let output = std::process::Command::new("ffprobe")
        .args([
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ])
        .output()
        .context("ffprobe не найден — установите FFmpeg и добавьте в PATH")?;

    if !output.status.success() {
        anyhow::bail!(
            "ffprobe завершился с ошибкой: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    let json: serde_json::Value =
        serde_json::from_slice(&output.stdout).context("не удалось распарсить вывод ffprobe")?;

    let duration = parse_duration(&json["format"]["duration"])
        .or_else(|| {
            json["streams"]
                .as_array()
                .and_then(|streams| streams.iter().find_map(|s| parse_duration(&s["duration"])))
        })
        .unwrap_or(0.0);

    let video_stream = json["streams"]
        .as_array()
        .and_then(|streams| streams.iter().find(|s| s["codec_type"] == "video"));

    let width = video_stream.and_then(|s| s["width"].as_i64()).unwrap_or(0) as i32;
    let height = video_stream.and_then(|s| s["height"].as_i64()).unwrap_or(0) as i32;

    let fps_str = video_stream
        .and_then(|s| s["r_frame_rate"].as_str())
        .unwrap_or("0/1");
    let fps = parse_fps(fps_str);

    let has_audio = json["streams"]
        .as_array()
        .map(|streams| streams.iter().any(|s| s["codec_type"] == "audio"))
        .unwrap_or(false);

    Ok(VideoInfo {
        duration,
        width,
        height,
        fps,
        has_audio,
    })
}

/// ffprobe отдаёт duration как строку ("15.000000"), а не как число.
fn parse_duration(value: &serde_json::Value) -> Option<f64> {
    value
        .as_f64()
        .or_else(|| value.as_str().and_then(|s| s.parse::<f64>().ok()))
}

fn parse_fps(s: &str) -> f64 {
    let parts: Vec<&str> = s.split('/').collect();
    if parts.len() == 2 {
        if let (Ok(a), Ok(b)) = (parts[0].parse::<f64>(), parts[1].parse::<f64>()) {
            if b != 0.0 {
                return a / b;
            }
        }
    }
    0.0
}

/// Находит закадровые моменты (highlights): пики энергии аудио + смены сцен.
pub fn detect_highlights(path: &str, max_duration: f64) -> Result<Vec<Highlight>> {
    let info = probe_video(path)?;
    if info.duration == 0.0 {
        return Ok(vec![]);
    }

    // Пики энергии аудио через ffmpeg astats
    let audio_peaks = detect::detect_audio_peaks(path)?;
    // Смены сцен
    let scene_changes = detect::detect_scene_changes(path)?;

    // Сливаем и ранжируем
    let mut candidates: Vec<(f64, f64, f64, String)> = Vec::new();
    for (start, _end, score) in audio_peaks {
        candidates.push((start, _end, score, "аудио-пик".to_string()));
    }
    for (start, _end, score) in scene_changes {
        candidates.push((start, _end, score, "смена сцены".to_string()));
    }

    // Сортируем по убыванию score
    candidates.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));

    // Нарезаем сегменты не пересекаясь, ограничиваем max_duration
    let mut highlights: Vec<Highlight> = Vec::new();
    let mut used_end = 0.0;
    for (start, _end, score, reason) in candidates {
        let s = start.max(used_end);
        let e = (s + max_duration.min(info.duration - s)).min(info.duration);
        if e - s < 5.0 {
            continue; // слишком короткий
        }
        used_end = e;
        highlights.push(Highlight {
            start: s,
            end: e,
            score,
            reason,
        });
        if highlights.len() >= 10 {
            break;
        }
    }

    highlights.sort_by(|a, b| {
        a.start
            .partial_cmp(&b.start)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    Ok(highlights)
}

/// Рендерит список клипов параллельно (Rayon). Каждый клип — отдельный вызов ffmpeg.
pub fn render_clips(
    source: &str,
    clips: &[ClipSegment],
    settings: &RenderSettings,
) -> Result<Vec<String>> {
    let preset = PRESETS
        .iter()
        .find(|p| p.name == settings.preset)
        .unwrap_or(&PRESETS[1]);

    let outputs: Result<Vec<String>> = clips
        .par_iter()
        .map(|clip| {
            let out = format!("rendered_{}.mp4", clip.id);
            render_single_clip(source, clip, preset, settings, &out)?;
            Ok(out)
        })
        .collect();

    outputs
}
