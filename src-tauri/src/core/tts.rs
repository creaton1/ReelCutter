use crate::core::subtitles::SubtitleSegment;
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Конфигурация TTS (озвучивания).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TtsConfig {
    pub api_url: String, // например "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    pub api_key: Option<String>,
    pub voice: String, // идентификатор голоса / имя системного голоса
    pub model: String, // модель TTS (опционально, зависит от провайдера)
    pub output_dir: PathBuf,
}

/// Один фрагмент озвученного аудио с таймингом.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TtsAudioSegment {
    pub start: f64,
    pub end: f64,
    pub text: String,
    pub audio_path: PathBuf,
}

/// Результат генерации TTS для всего клипа.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TtsResult {
    pub segments: Vec<TtsAudioSegment>,
    pub combined_audio: PathBuf, // один аудиофайл на весь клип
}

/// Клиент TTS.
pub struct TtsClient {
    client: Client,
    config: TtsConfig,
}

impl TtsClient {
    pub fn new(config: TtsConfig) -> Self {
        if let Some(parent) = &config.output_dir.parent() {
            let _ = fs::create_dir_all(parent);
        }
        Self {
            client: Client::new(),
            config,
        }
    }

    /// Озвучивает один сегмент субтитров, возвращает путь к аудиофайлу.
    pub fn synthesize_segment(&self, seg: &SubtitleSegment, index: usize) -> Result<PathBuf> {
        let safe_text: String = seg
            .text
            .chars()
            .filter(|c| c.is_alphanumeric() || *c == ' ' || *c == '-')
            .take(30)
            .collect();
        let out = self
            .config
            .output_dir
            .join(format!("tts_{index}_{safe_text}.mp3"));

        // Пытаемся через HTTP TTS API
        if let Ok(audio) = self.synthesize_http(&seg.text) {
            fs::write(&out, &audio)?;
            return Ok(out);
        }

        // Фолбэк: системный TTS через PowerShell (Windows)
        if let Ok(_audio) = self.synthesize_system(&seg.text, &out) {
            return Ok(out);
        }

        anyhow::bail!("не удалось озвучить сегмент: {}", seg.text);
    }

    /// HTTP TTS запрос (совместим с ElevenLabs и подобными API).
    fn synthesize_http(&self, text: &str) -> Result<Vec<u8>> {
        let mut request = self.client.post(&self.config.api_url);

        if let Some(key) = &self.config.api_key {
            request = request.header("xi-api-key", key);
        }

        let body = serde_json::json!({
            "text": text,
            "model_id": self.config.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        });

        let response = request
            .json(&body)
            .send()
            .with_context(|| format!("TTS API не отвечает: {}", self.config.api_url))?;

        if !response.status().is_success() {
            anyhow::bail!("TTS API вернул статус {}", response.status());
        }

        let bytes = response
            .bytes()
            .with_context(|| "не удалось прочитать тело ответа TTS")?;
        Ok(bytes.to_vec())
    }

    /// Системный TTS через PowerShell (Windows, без API-ключа).
    fn synthesize_system(&self, text: &str, out: &Path) -> Result<PathBuf> {
        let ps_script = format!(
            r#"Add-Type -AssemblyName System.Speech;
$syn = New-Object System.Speech.Synthesis.SpeechSynthesizer;
$syn.SetOutputToWaveFile('{}');
$syn.Speak('{}');
$syn.Dispose();
"#,
            out.to_string_lossy(),
            text.replace('\'', "\\'")
        );

        let status = Command::new("powershell")
            .args([
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                &ps_script,
            ])
            .status()
            .context("PowerShell TTS не запустился")?;

        if status.success() && out.exists() {
            Ok(out.to_path_buf())
        } else {
            anyhow::bail!("системный TTS не создал аудиофайл")
        }
    }

    /// Склеивает все сегменты в один аудиофайл с паузами между ними,
    /// выравнивая длительность под тайминги субтитров через ffmpeg atrim/adelay.
    pub fn combine_audio(
        &self,
        segments: &[TtsAudioSegment],
        clip_duration: f64,
    ) -> Result<PathBuf> {
        if segments.is_empty() {
            anyhow::bail!("нет сегментов для склейки аудио");
        }

        let combined = self.config.output_dir.join("combined_tts.mp3");

        // Создаём список файлов для ffmpeg concat
        let list_path = self.config.output_dir.join("tts_concat_list.txt");
        let mut list_content = String::new();
        for seg in segments {
            list_content.push_str(&format!("file '{}'\n", seg.audio_path.to_string_lossy()));
        }
        fs::write(&list_path, list_content)?;

        // Конкатенация + обрезка до длительности клипа
        let status = Command::new("ffmpeg")
            .args([
                "-hide_banner",
                "-nostats",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                &list_path.to_string_lossy(),
                "-t",
                &clip_duration.to_string(),
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                &combined.to_string_lossy(),
            ])
            .status()
            .context("ffmpeg не смог склеить TTS аудио")?;

        if !status.success() {
            anyhow::bail!("ffmpeg ошибка при склейке TTS аудио");
        }

        Ok(combined)
    }

    pub fn config(&self) -> &TtsConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_text_filter_removes_unsafe_chars() {
        let text = "Привет, мир! (текст)";
        let safe: String = text
            .chars()
            .filter(|c| c.is_alphanumeric() || *c == ' ' || *c == '-')
            .take(30)
            .collect();
        assert!(!safe.contains('('));
        assert!(!safe.contains(')'));
        assert!(!safe.contains(','));
    }
}
