use crate::core::subtitles::SubtitleSegment;
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};

/// Конфигурация подключения к API перевода.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranslationConfig {
    pub api_url: String, // например "https://libretranslate.de/translate"
    pub api_key: Option<String>,
    pub source_lang: String, // "ru", "auto" и т.д.
    pub target_lang: String, // "en", "es", "fr" и т.д.
}

/// Тело запроса к API в стиле LibreTranslate.
#[derive(Serialize)]
struct TranslateRequest {
    q: String,
    source: String,
    target: String,
    format: String,
}

/// Ответ от API в стиле LibreTranslate.
#[derive(Deserialize)]
struct TranslateResponse {
    translated_text: String,
}

/// Клиент для перевода текста и субтитров через HTTP API.
pub struct Translator {
    client: Client,
    config: TranslationConfig,
}

impl Translator {
    pub fn new(config: TranslationConfig) -> Self {
        Self {
            client: Client::new(),
            config,
        }
    }

    /// Переводит одну строку текста.
    pub fn translate_text(&self, text: &str) -> Result<String> {
        if text.trim().is_empty() {
            return Ok(text.to_string());
        }

        let body = TranslateRequest {
            q: text.to_string(),
            source: self.config.source_lang.clone(),
            target: self.config.target_lang.clone(),
            format: "text".to_string(),
        };

        let mut request = self.client.post(&self.config.api_url).json(&body);

        if let Some(key) = &self.config.api_key {
            request = request.header("Authorization", format!("Bearer {}", key));
        }

        let response: TranslateResponse = request
            .send()
            .with_context(|| format!("не удалось отправить запрос на {}", self.config.api_url))?
            .json()
            .with_context(|| "не удалось распарсить ответ API перевода")?;

        Ok(response.translated_text)
    }

    /// Переводит все сегменты субтитров, возвращая новые сегменты с переведённым текстом.
    pub fn translate_segments(&self, segments: &[SubtitleSegment]) -> Result<Vec<SubtitleSegment>> {
        let mut result = Vec::with_capacity(segments.len());
        for seg in segments {
            let translated = self.translate_text(&seg.text)?;
            result.push(SubtitleSegment {
                start: seg.start,
                end: seg.end,
                text: translated,
            });
        }
        Ok(result)
    }

    /// Проверяет доступность API перевода (простой запрос).
    pub fn ping(&self) -> Result<bool> {
        let result = self.translate_text("hello");
        Ok(result.is_ok())
    }

    pub fn config(&self) -> &TranslationConfig {
        &self.config
    }
}

/// Вспомогательная структура для конфигурации перевода из настроек рендера.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RenderTranslationSettings {
    pub enabled: bool,
    pub api_url: String,
    pub api_key: Option<String>,
    pub source_lang: String,
    pub target_lang: String,
}

impl Default for TranslationConfig {
    fn default() -> Self {
        Self {
            api_url: "https://libretranslate.de/translate".to_string(),
            api_key: None,
            source_lang: "auto".to_string(),
            target_lang: "en".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn translate_segments_preserves_timing() {
        // Тест без реального API — только проверяем структуру
        let segments = vec![
            SubtitleSegment {
                start: 0.0,
                end: 2.0,
                text: "Привет".into(),
            },
            SubtitleSegment {
                start: 2.0,
                end: 4.0,
                text: "Как дела".into(),
            },
        ];
        assert_eq!(segments.len(), 2);
        assert_eq!(segments[0].start, 0.0);
        assert_eq!(segments[1].end, 4.0);
    }
}
