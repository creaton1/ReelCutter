use anyhow::{Context, Result};
use std::process::Command;

/// Ищет пики энергии аудио через ffmpeg astats.
/// Возвращает список (start, end, score), где score в [0.0, 1.0].
pub fn detect_audio_peaks(path: &str) -> Result<Vec<(f64, f64, f64)>> {
    let output = Command::new("ffmpeg")
        .args([
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-af",
            "astats=metadata=1,ametadata=mode=print:file=-",
            "-f",
            "null",
            "-",
        ])
        .output()
        .context("ffmpeg не найден — установите FFmpeg и добавьте в PATH")?;

    if !output.status.success() {
        anyhow::bail!(
            "ffmpeg astats завершился с ошибкой: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    let text = String::from_utf8_lossy(&output.stdout);
    let mut peaks: Vec<(f64, f64, f64)> = Vec::new();
    let mut current_time: Option<f64> = None;

    // astats с ametadata=mode=print:file=- выдаёт блоки вида:
    // frame:0    pts:0       pts_time:0
    // lavfi.astats.1.RMS_level=-20.232022
    // ...
    for line in text.lines() {
        if let Some(t) = extract_pts_time(line) {
            current_time = Some(t);
            continue;
        }
        if let Some(rms) = extract_rms_level(line) {
            let t = current_time.unwrap_or(0.0);
            let score = score_from_rms(rms);
            if score > 0.25 {
                peaks.push((t, t, score));
            }
            current_time = None;
        }
    }

    // Склеиваем близкие пики в один сегмент
    Ok(merge_close_events(peaks))
}

/// Ищет смены сцен через ffmpeg select + showinfo.
pub fn detect_scene_changes(path: &str) -> Result<Vec<(f64, f64, f64)>> {
    let output = Command::new("ffmpeg")
        .args([
            "-hide_banner",
            "-i",
            path,
            "-filter_complex",
            "[0:v]select='gt(scene,0.3)',showinfo",
            "-f",
            "null",
            "-",
        ])
        .output()
        .context("ffmpeg не найден — установите FFmpeg и добавьте в PATH")?;

    if !output.status.success() {
        anyhow::bail!(
            "ffmpeg scene detect завершился с ошибкой: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    let text = String::from_utf8_lossy(&output.stderr);
    let mut scenes: Vec<(f64, f64, f64)> = Vec::new();

    // showinfo печатает строки вида:
    // [Parsed_showinfo_0 @ ...] n:   0 pts:... pts_time:12.000 ...
    for line in text.lines() {
        if !line.contains("pts_time:") {
            continue;
        }
        let time = extract_pts_time(line);
        if time.is_none() {
            continue;
        }
        scenes.push((time.unwrap(), time.unwrap(), 0.7));
    }

    Ok(merge_close_events(scenes))
}

/// Склеивает события, идущие подряд (в пределах 1 секунды), в один сегмент.
fn merge_close_events(events: Vec<(f64, f64, f64)>) -> Vec<(f64, f64, f64)> {
    let mut sorted: Vec<(f64, f64, f64)> = events;
    sorted.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

    let mut merged: Vec<(f64, f64, f64)> = Vec::new();
    for (start, _end, score) in sorted {
        if let Some(last) = merged.last_mut() {
            if start - last.1 <= 1.0 {
                last.1 = start;
                last.2 = last.2.max(score);
                continue;
            }
        }
        merged.push((start, start, score));
    }
    merged
}

fn extract_pts_time(line: &str) -> Option<f64> {
    let marker = "pts_time:";
    let idx = line.find(marker)?;
    let rest = &line[idx + marker.len()..];
    let end = rest.find(' ').unwrap_or(rest.len());
    rest[..end].trim().parse::<f64>().ok()
}

fn extract_rms_level(line: &str) -> Option<f64> {
    let marker = "lavfi.astats.1.RMS_level=";
    let idx = line.find(marker)?;
    let rest = &line[idx + marker.len()..];
    let end = rest.find(' ').unwrap_or(rest.len());
    rest[..end].trim().parse::<f64>().ok()
}

/// Превращает RMS (дБ) в score [0, 1]: -60 дБ и ниже → 0, -10 дБ и выше → 1.
pub(crate) fn score_from_rms(rms: f64) -> f64 {
    ((rms + 60.0) / 50.0).clamp(0.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_pts_time_parses_value() {
        let line = "frame:12345  pts:900000  pts_time:30.000  lavfi.scene.score=0.45";
        assert_eq!(extract_pts_time(line), Some(30.0));
    }

    #[test]
    fn extract_pts_time_parses_showinfo_value() {
        let line = "[Parsed_showinfo_0 @ 000001] n:   0 pts: 3600 pts_time:12.000";
        assert_eq!(extract_pts_time(line), Some(12.0));
    }

    #[test]
    fn extract_pts_time_returns_none_when_missing() {
        assert_eq!(extract_pts_time("frame:12345  pts:900000"), None);
    }

    #[test]
    fn extract_rms_level_parses_value() {
        let line = "lavfi.astats.1.RMS_level=-20.232022";
        assert_eq!(extract_rms_level(line), Some(-20.232022));
    }

    #[test]
    fn merge_close_events_joins_nearby_events() {
        let events = vec![(10.0, 10.0, 0.5), (10.5, 10.5, 0.8), (25.0, 25.0, 0.6)];
        let merged = merge_close_events(events);
        assert_eq!(merged.len(), 2);
        assert_eq!(merged[0], (10.0, 10.5, 0.8));
        assert_eq!(merged[1], (25.0, 25.0, 0.6));
    }

    #[test]
    fn rms_score_bounds() {
        assert_eq!(score_from_rms(-60.0), 0.0);
        assert_eq!(score_from_rms(-10.0), 1.0);
        assert_eq!(score_from_rms(-100.0), 0.0);
    }
}
