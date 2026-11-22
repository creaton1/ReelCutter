use crate::core::subtitles::{ass_color, select_subtitles_for_clip, write_ass, SubtitleSegment};
use crate::core::types::*;
use anyhow::{Context, Result};
use std::fs;
use std::process::Command;

/// Собирает аргументы командной строки ffmpeg для рендера одного клипа с учётом настроек.
pub(crate) fn render_single_clip(
    source: &str,
    clip: &ClipSegment,
    preset: &PlatformPreset,
    settings: &RenderSettings,
    output: &str,
    subtitle_segments: &[SubtitleSegment],
    dub_audio_path: Option<&str>,
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

    // Дублирование (TTS аудио) — добавляем как отдельный вход
    let mut dub_input: Option<usize> = None;
    if let Some(dub_path) = dub_audio_path {
        cmd.args(["-i", dub_path]);
        dub_input = Some(inputs);
        inputs += 1;
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

    // Субтитры: реальный текст из Whisper (+ перевод, если включён)
    let ass_path = if settings.subtitles {
        let selected = select_subtitles_for_clip(subtitle_segments, clip.start, clip.end);
        let dir = std::env::temp_dir().join("reelcutter");
        let p = write_ass(&selected, settings, &dir, &clip.id)?;
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
    let audio_map = if let Some(di) = dub_input {
        // Дублирование: используем TTS аудио вместо оригинальной дорожки
        format!("[{di}:a]")
    } else {
        let mut map = String::from("0:a?");
        if let Some(mi) = music_input {
            let volume = settings.music_volume.clamp(0.0, 1.0);
            audio_filters.push(format!("[{mi}:a]volume={volume}[bgaudio]"));
            audio_filters.push(
                "[0:a][bgaudio]amix=inputs=2:duration=first:dropout_transition=2[outa]".to_string(),
            );
            map = String::from("[outa]");
        }
        map
    };

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
    fn score_from_rms_used_in_render_module() {
        // только проверка, что функция доступна и корректна
        assert_eq!(score_from_rms(-60.0), 0.0);
        assert_eq!(score_from_rms(-10.0), 1.0);
    }
}
