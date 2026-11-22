use crate::core::types::*;
use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Один сегмент субтитров с таймингами.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubtitleSegment {
    pub start: f64,
    pub end: f64,
    pub text: String,
}

/// Конфигурация генерации субтитров через встроенный whisper-фильтр FFmpeg.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubtitleConfig {
    pub model_path: String,    // путь к .bin модели whisper.cpp
    pub language: String,      // "auto" или код языка (ru, en и т.д.)
    pub translate_to_en: bool, // перевести ли речь на английский (встроенное в whisper)
    pub output_format: String, // "srt" | "json" | "text"
}

/// Результат генерации субтитров.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubtitleResult {
    pub segments: Vec<SubtitleSegment>,
    pub language_detected: Option<String>,
    pub output_path: PathBuf,
}

/// Генерирует субтитры из аудио дорожки видео через встроенный фильтр `whisper` FFmpeg.
/// Записывает SRT-файл по указанному пути и возвращает распарсенные сегменты.
pub fn generate_subtitles(video_path: &str, config: &SubtitleConfig) -> Result<SubtitleResult> {
    let output_path = if config.output_format == "srt" {
        PathBuf::from(video_path.to_string() + ".srt")
    } else {
        PathBuf::from(format!("{video_path}.subs.{}", config.output_format))
    };

    let mut cmd = Command::new("ffmpeg");
    cmd.arg("-hide_banner")
        .arg("-nostats")
        .arg("-y")
        .arg("-i")
        .arg(video_path)
        // whisper filter: аудио на входе, аудио на выходе (passthrough), субтитры пишем в destination
        .arg("-filter_complex")
        .arg(format!(
            "whisper=model={}:language={}:translate={}:format={}:destination={}",
            config.model_path,
            config.language,
            config.translate_to_en,
            config.output_format,
            output_path.to_string_lossy().replace('\\', "/")
        ))
        .arg("-map")
        .arg("0:a?")
        .arg("-f")
        .arg("null")
        .arg("-");

    let status = cmd.status().context("ffmpeg whisper не запустился")?;
    if !status.success() {
        anyhow::bail!(
            "FFmpeg whisper завершился с ошибкой. Убедитесь, что модель whisper доступна по пути: {}",
            config.model_path
        );
    }

    let segments = parse_srt(&output_path)
        .unwrap_or_default()
        .into_iter()
        .map(|(start, end, text)| SubtitleSegment { start, end, text })
        .collect();

    Ok(SubtitleResult {
        segments,
        language_detected: None,
        output_path,
    })
}

/// Парсит SRT-файл в вектор (start_sec, end_sec, text).
pub fn parse_srt(path: &Path) -> Result<Vec<(f64, f64, String)>> {
    let content = fs::read_to_string(path)
        .with_context(|| format!("не удалось прочитать SRT: {}", path.display()))?;

    let mut segments: Vec<(f64, f64, String)> = Vec::new();
    let blocks: Vec<&str> = content.split("\n\n").collect();

    for block in blocks {
        let lines: Vec<&str> = block.lines().collect();
        if lines.len() < 3 {
            continue;
        }

        let timing = lines[1].trim();
        if let Some((start, end)) = parse_srt_timing(timing) {
            let text = lines[2..].join("\n").trim().to_string();
            if !text.is_empty() {
                segments.push((start, end, text));
            }
        }
    }

    Ok(segments)
}

/// Парсит одну строку тайминга SRT в секунды.
fn parse_srt_timing(timing: &str) -> Option<(f64, f64)> {
    let parts: Vec<&str> = timing.split(" --> ").collect();
    if parts.len() != 2 {
        return None;
    }
    let start = parse_srt_timecode(parts[0].trim())?;
    let end = parse_srt_timecode(parts[1].trim())?;
    Some((start, end))
}

fn parse_srt_timecode(tc: &str) -> Option<f64> {
    let parts: Vec<&str> = tc.split(':').collect();
    if parts.len() != 3 {
        return None;
    }
    let hours: f64 = parts[0].trim().parse().ok()?;
    let minutes: f64 = parts[1].trim().parse().ok()?;
    let sec_parts: Vec<&str> = parts[2].split(',').collect();
    let seconds: f64 = sec_parts[0].trim().parse().ok()?;
    let millis: f64 = sec_parts.get(1)?.trim().parse().ok()?;
    Some(hours * 3600.0 + minutes * 60.0 + seconds + millis / 1000.0)
}

/// Генерирует .ass файл из сегментов субтитров с настройками стиля.
pub fn write_ass(
    segments: &[SubtitleSegment],
    settings: &RenderSettings,
    dir: &Path,
    clip_id: &str,
) -> Result<PathBuf> {
    fs::create_dir_all(dir)?;
    let path = dir.join(format!("subs_{}.ass", clip_id));

    let primary = ass_color(&settings.subtitle_color);
    let outline = "&H00000000&";

    let style_line = format!(
        "Style: Default,{},{},{},{},&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,30,1",
        settings.subtitle_font, settings.subtitle_size, primary, outline
    );

    let mut content = String::new();
    content.push_str("[Script Info]\n");
    content.push_str("Title: ReelCutter Subtitles\n");
    content.push_str("ScriptType: v4.00+\n");
    content.push_str("WrapStyle: 0\n");
    content.push_str("ScaledBorderAndShadow: yes\n");
    content.push_str("YCbCr Matrix: TV.709\n\n");
    content.push_str("[V4+ Styles]\n");
    content.push_str("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n");
    content.push_str(&style_line);
    content.push_str("\n\n[Events]\n");
    content.push_str(
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n",
    );

    for seg in segments {
        let start = ass_time(seg.start);
        let end = ass_time(seg.end);
        let text = seg.text.replace('{', "\\{").replace('}', "\\}");
        content.push_str(&format!(
            "Dialogue: 0,{start},{end},Default,,0,0,0,,{{\\pos(preset_w*0.5, preset_h*0.92)}}{text}\n"
        ));
    }

    fs::write(&path, content)?;
    Ok(path)
}

/// Цвет #RRGGBB → ASS &HBBGGRR&.
pub(crate) fn ass_color(hex: &str) -> String {
    let hex = hex.trim_start_matches('#');
    let bytes = u32::from_str_radix(hex, 16).unwrap_or(0xFFFFFF);
    let r = ((bytes >> 16) & 0xFF) as u8;
    let g = ((bytes >> 8) & 0xFF) as u8;
    let b = (bytes & 0xFF) as u8;
    format!("&H{:02X}{:02X}{:02X}&", b, g, r)
}

/// Время в формате ASS: h:mm:ss.cc
fn ass_time(secs: f64) -> String {
    let total = secs.max(0.0);
    let h = (total / 3600.0) as i64;
    let m = ((total % 3600.0) / 60.0) as i64;
    let s = (total % 60.0) as i64;
    let c = (total.fract() * 100.0) as i64;
    format!("{h}:{m:02}:{s:02}.{c:02}")
}

/// Выбирает сегменты субтитров, попадающие в диапазон клипа (с наложением).
pub fn select_subtitles_for_clip(
    segments: &[SubtitleSegment],
    clip_start: f64,
    clip_end: f64,
) -> Vec<SubtitleSegment> {
    segments
        .iter()
        .filter(|s| s.start < clip_end && s.end > clip_start)
        .cloned()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_srt_timecode_basic() {
        assert_eq!(parse_srt_timecode("00:00:01,500"), Some(1.5));
        assert_eq!(parse_srt_timecode("01:02:03,456"), Some(3723.456));
        assert_eq!(parse_srt_timecode("00:00:00,000"), Some(0.0));
    }

    #[test]
    fn parse_srt_timing_basic() {
        let result = parse_srt_timing("00:00:01,500 --> 00:00:04,200");
        assert_eq!(result, Some((1.5, 4.2)));
    }

    #[test]
    fn select_subtitles_for_clip_filters_correctly() {
        let segments = vec![
            SubtitleSegment {
                start: 0.0,
                end: 2.0,
                text: "first".into(),
            },
            SubtitleSegment {
                start: 5.0,
                end: 7.0,
                text: "second".into(),
            },
            SubtitleSegment {
                start: 10.0,
                end: 12.0,
                text: "third".into(),
            },
        ];
        let selected = select_subtitles_for_clip(&segments, 4.0, 6.0);
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0].text, "second");
    }

    #[test]
    fn ass_time_formats_correctly() {
        assert_eq!(ass_time(0.0), "0:00:00.00");
        assert_eq!(ass_time(5.5), "0:00:05.50");
        assert_eq!(ass_time(61.25), "0:01:01.25");
    }
}
