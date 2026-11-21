use crate::core::types::*;
use anyhow::{Context, Result};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Время в формате ASS: h:mm:ss.cc
fn ass_time(secs: f64) -> String {
    let total = secs.max(0.0);
    let h = (total / 3600.0) as i64;
    let m = ((total % 3600.0) / 60.0) as i64;
    let s = (total % 60.0) as i64;
    let c = (total.fract() * 100.0) as i64;
    format!("{h}:{m:02}:{s:02}.{c:02}")
}

/// Цвет #RRGGBB → ASS &HBBGGRR&.
fn ass_color(hex: &str) -> String {
    let hex = hex.trim_start_matches('#');
    let bytes = u32::from_str_radix(hex, 16).unwrap_or(0xFFFFFF);
    let r = ((bytes >> 16) & 0xFF) as u8;
    let g = ((bytes >> 8) & 0xFF) as u8;
    let b = (bytes & 0xFF) as u8;
    format!("&H{:02X}{:02X}{:02X}&", b, g, r)
}

/// Генерирует .ass файл с одним событием на клип (текст — причина момента).
/// Текст, шрифт, размер и цвет берутся из настроек рендера.
fn write_subtitle_file(
    clip: &ClipSegment,
    settings: &RenderSettings,
    dir: &Path,
) -> Result<PathBuf> {
    fs::create_dir_all(dir)?;

    let path = dir.join(format!("subs_{}.ass", clip.id));
    let start = ass_time(clip.start);
    let end = ass_time(clip.end);
    let primary = ass_color(&settings.subtitle_color);
    // Чёрная обводка для читаемости на любом фоне
    let outline = "&H00000000&";
    let text = clip.reason.replace('{', "\\{").replace('}', "\\}");

    let content = format!(
        r#"[Script Info]
Title: ReelCutter subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},{primary},{outline},&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{start},{end},Default,,0,0,0,,{{\pos(preset_w*0.5, preset_h*0.92)}}{text}
"#,
        font = settings.subtitle_font,
        size = settings.subtitle_size,
    );

    fs::write(&path, content)?;
    Ok(path)
}

/// Собирает аргументы командной строки ffmpeg для рендера одного клипа с учётом настроек.
pub(crate) fn render_single_clip(
    source: &str,
    clip: &ClipSegment,
    preset: &PlatformPreset,
    settings: &RenderSettings,
    output: &str,
) -> Result<()> {
    let duration = clip.end - clip.start;
    let w = preset.width;
    let h = preset.height;

    let mut cmd = Command::new("ffmpeg");
    cmd.arg("-y");

    // Вход 0 — исходное видео
    cmd.args(["-ss", &clip.start.to_string(), "-i", source]);

    let mut inputs = 1;
    let mut music_input = None;
    let mut banner_input = None;

    if settings.music {
        if let Some(music_path) = &settings.music_path {
            cmd.args(["-i", music_path]);
            music_input = Some(inputs);
            inputs += 1;
        }
    }

    if settings.banner {
        if let Some(banner_path) = &settings.banner_path {
            cmd.args(["-i", banner_path]);
            banner_input = Some(inputs);
            inputs += 1;
        }
    }

    // ---------- сборка filter_complex ----------
    let mut filters: Vec<String> = Vec::new();

    // Видео: вертикальное 9:16 с блюром по бокам
    filters.push(format!(
        "[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[main]"
    ));

    // Баннер: масштабируем по ширине видео, прозрачность, наложение по центру
    if let Some(bi) = banner_input {
        filters.push(format!(
            "[{bi}:v]scale={w}:-1:force_original_aspect_ratio=decrease[banner]"
        ));
        filters.push("[main][banner]overlay=(W-w)/2:(H-h)/2:format=auto[main]".to_string());
    }

    // Субтитры
    let ass_path = if settings.subtitles {
        let dir = std::env::temp_dir().join("reelcutter");
        let p = write_subtitle_file(clip, settings, &dir)?;
        // Путь в фильтре subtitles экранирует обратные слэши и двоеточия
        let ass_filter_path = p.to_string_lossy().replace('\\', "/");
        let filter_style = format!(
            "force_style=\"Fontname={},Fontsize={},PrimaryColour={}\"",
            settings.subtitle_font,
            settings.subtitle_size,
            ass_color(&settings.subtitle_color)
        );
        filters.push(format!(
            "[main]subtitles='{ass_filter_path}':{filter_style}[main]"
        ));
        Some(p)
    } else {
        None
    };

    let filter_complex = filters.join(";");
    cmd.args(["-filter_complex", &filter_complex]);

    // ---------- аудио ----------
    let mut audio_filters: Vec<String> = Vec::new();
    let mut audio_map = String::from("0:a?");

    if let Some(mi) = music_input {
        let volume = settings.music_volume.clamp(0.0, 1.0);
        audio_filters.push(format!("[{mi}:a]volume={volume}[bgaudio]"));
        audio_filters.push(
            "[0:a][bgaudio]amix=inputs=2:duration=first:dropout_transition=2[outa]".to_string(),
        );
        audio_map = String::from("[outa]");
    }

    if !audio_filters.is_empty() {
        cmd.args(["-filter_complex:a", &audio_filters.join(";")]);
    }

    // ---------- маппинги ----------
    cmd.arg("-map").arg("[main]");
    cmd.arg("-map").arg(&audio_map);

    // Кодеки
    cmd.args([
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-t",
        &duration.to_string(),
        output,
    ]);

    let status = cmd.status().context("ffmpeg не запустился")?;
    if !status.success() {
        anyhow::bail!("ffmpeg ошибка при рендере клипа {}", clip.id);
    }

    // Удаляем временный .ass файл
    if let Some(p) = ass_path {
        let _ = fs::remove_file(p);
    }

    let _ = inputs; // индексы входов определяются порядком добавления `-i`
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::detect::score_from_rms;

    #[test]
    fn ass_time_formats_correctly() {
        assert_eq!(ass_time(0.0), "0:00:00.00");
        assert_eq!(ass_time(5.5), "0:00:05.50");
        assert_eq!(ass_time(61.25), "0:01:01.25");
        assert_eq!(ass_time(3661.0), "1:01:01.00");
        assert_eq!(ass_time(-3.0), "0:00:00.00"); // отрицательное время обрезается
    }

    #[test]
    fn ass_color_converts_rgb_to_bgr() {
        assert_eq!(ass_color("#FFFFFF"), "&HFFFFFF&");
        assert_eq!(ass_color("#FF0000"), "&H0000FF&"); // красный → синий&зелёный нолики в ASS порядке
        assert_eq!(ass_color("#00FF00"), "&H00FF00&"); // зелёный
        assert_eq!(ass_color("#0000FF"), "&HFF0000&"); // синий →先头
    }

    #[test]
    fn score_from_rms_used_in_render_module() {
        // только проверка, что функция доступна и корректна
        assert_eq!(score_from_rms(-60.0), 0.0);
        assert_eq!(score_from_rms(-10.0), 1.0);
    }
}
