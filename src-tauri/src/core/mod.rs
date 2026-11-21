pub mod analyzer;
pub mod ffmpeg;
pub mod types;

use crate::core::types::*;
use anyhow::{Context, Result};
use rayon::prelude::*;

/// Анализирует видеофайл и возвращает информацию о нём (длительность, размер, FPS, аудио).
pub fn probe_video(path: &str) -> Result<VideoInfo> {
    let output = std::process::Command::new("ffprobe")
        .args([
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            path,
        ])
        .output()
        .context("ffprobe не найден — установите FFmpeg и добавьте в PATH")?;

    if !output.status.success() {
        anyhow::bail!("ffprobe завершился с ошибкой: {}", String::from_utf8_lossy(&output.stderr));
    }

    let json: serde_json::Value = serde_json::from_slice(&output.stdout)
        .context("не удалось распарсить вывод ffprobe")?;

    let duration = json["format"]["duration"]
        .as_f64()
        .or_else(|| json["streams"][0]["duration"].as_f64())
        .unwrap_or(0.0);

    let width = json["streams"][0]["width"].as_i64().unwrap_or(0) as i32;
    let height = json["streams"][0]["height"].as_i64().unwrap_or(0) as i32;

    let fps_str = json["streams"][0]["r_frame_rate"].as_str().unwrap_or("0/1");
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
    let audio_peaks = detect_audio_peaks(path)?;
    // Смены сцен
    let scene_changes = detect_scene_changes(path)?;

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

    highlights.sort_by(|a, b| a.start.partial_cmp(&b.start).unwrap_or(std::cmp::Ordering::Equal));
    Ok(highlights)
}

fn detect_audio_peaks(_path: &str) -> Result<Vec<(f64, f64, f64)>> {
    // Упрощённая заглушка: в реальности здесь парсинг ffmpeg astats/ebur128.
    // Возвращаем равномерно распределённые candidates для демонстрации.
    Ok(vec![
        (10.0, 20.0, 0.9),
        (45.0, 55.0, 0.85),
        (90.0, 100.0, 0.8),
    ])
}

fn detect_scene_changes(_path: &str) -> Result<Vec<(f64, f64, f64)>> {
    // Заглушка scene detection. Реализация через ffmpeg select='gt(scene,0.3)'.
    Ok(vec![
        (30.0, 40.0, 0.75),
        (70.0, 80.0, 0.7),
    ])
}

/// Рендерит список клипов параллельно (Rayon). Каждый клип — отдельный вызов ffmpeg.
pub fn render_clips(
    source: &str,
    clips: &[ClipSegment],
    settings: &RenderSettings,
) -> Result<Vec<String>> {
    let preset = PRESETS.iter().find(|p| p.name == settings.preset).unwrap_or(&PRESETS[1]);

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

/// Рендерит один клип через ffmpeg (вертикальное 9:16 с блюром по бокам).
pub(crate) fn render_single_clip(
    source: &str,
    clip: &ClipSegment,
    preset: &PlatformPreset,
    _settings: &RenderSettings,
    output: &str,
) -> Result<()> {
    let duration = clip.end - clip.start;
    let filter = build_vertical_filter(preset)?;
    let mut cmd = std::process::Command::new("ffmpeg");
    cmd.args([
        "-y",
        "-ss", &clip.start.to_string(),
        "-i", source,
        "-t", &duration.to_string(),
        "-filter_complex", &filter,
        "-map", "[out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output,
    ]);

    let status = cmd.status().context("ffmpeg не запустился")?;
    if !status.success() {
        anyhow::bail!("ffmpeg ошибка при рендере клипа {}", clip.id);
    }
    Ok(())
}

fn build_vertical_filter(preset: &PlatformPreset) -> Result<String> {
    // 9:16 с блюром по бокам и центрированием основного видео
    let w = preset.width;
    let h = preset.height;
    Ok(format!(
        "[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[main];\
         [0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,boxblur=luma_radius=40:luma_power=1[bg];\
         [bg][main]overlay=(W-w)/2:(H-h)/2[out]"
    ))
}
