use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformPreset {
    pub name: &'static str,
    pub max_duration: f64,
    pub width: u32,
    pub height: u32,
}

impl Default for PlatformPreset {
    fn default() -> Self {
        PlatformPreset {
            name: "Shorts",
            max_duration: 60.0,
            width: 1080,
            height: 1920,
        }
    }
}

pub const PRESETS: [PlatformPreset; 4] = [
    PlatformPreset {
        name: "Reels",
        max_duration: 90.0,
        width: 1080,
        height: 1920,
    },
    PlatformPreset {
        name: "Shorts",
        max_duration: 60.0,
        width: 1080,
        height: 1920,
    },
    PlatformPreset {
        name: "TikTok",
        max_duration: 60.0,
        width: 1080,
        height: 1920,
    },
    PlatformPreset {
        name: "VK Clips",
        max_duration: 60.0,
        width: 1080,
        height: 1920,
    },
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Highlight {
    pub start: f64,
    pub end: f64,
    pub score: f64,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipSegment {
    pub id: String,
    pub project_id: Option<String>,
    pub start: f64,
    pub end: f64,
    pub score: f64,
    pub reason: String,
    pub output_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenderSettings {
    pub preset: String,
    pub subtitles: bool,
    pub subtitle_font: String,
    pub subtitle_size: i32,
    pub subtitle_color: String,
    pub subtitle_language: String, // "auto", "ru", "en" — язык распознавания
    pub translation_enabled: bool, // переводить ли субтитры
    pub translation_target_lang: String, // "en", "es", "fr" и т.д.
    pub translation_api_url: String, // URL API перевода (LibreTranslate)
    pub translation_api_key: Option<String>,
    pub dubbing_enabled: bool, // дублирование звука (TTS вместо оригинального аудио)
    pub tts_api_url: String,   // URL TTS API (ElevenLabs и др.)
    pub tts_api_key: Option<String>,
    pub tts_voice: String, // идентификатор голоса
    pub tts_model: String, // модель TTS
    pub banner: bool,
    pub banner_path: Option<String>,
    pub banner_opacity: f32,
    pub music: bool,
    pub music_path: Option<String>,
    pub music_volume: f32,
}

impl Default for RenderSettings {
    fn default() -> Self {
        RenderSettings {
            preset: "Shorts".to_string(),
            subtitles: true,
            subtitle_font: "Arial".to_string(),
            subtitle_size: 24,
            subtitle_color: "#FFFFFF".to_string(),
            subtitle_language: "auto".to_string(),
            translation_enabled: false,
            translation_target_lang: "en".to_string(),
            translation_api_url: "https://libretranslate.de/translate".to_string(),
            translation_api_key: None,
            dubbing_enabled: false,
            tts_api_url: "https://api.elevenlabs.io/v1/text-to-speech/".to_string(),
            tts_api_key: None,
            tts_voice: "Rachel".to_string(),
            tts_model: "eleven_multilingual_v2".to_string(),
            banner: false,
            banner_path: None,
            banner_opacity: 0.5,
            music: false,
            music_path: None,
            music_volume: 0.3,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoInfo {
    pub duration: f64,
    pub width: i32,
    pub height: i32,
    pub fps: f64,
    pub has_audio: bool,
}
