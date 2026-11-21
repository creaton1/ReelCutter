"""Конфигурация приложения"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import json


@dataclass
class PlatformConfig:
    """Настройки для каждой платформы"""
    name: str
    width: int
    height: int
    max_duration: int  # секунды
    aspect_ratio: str = "9:16"

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)


PLATFORMS = {
    "reels": PlatformConfig("Instagram Reels", 1080, 1920, 90),
    "shorts": PlatformConfig("YouTube Shorts", 1080, 1920, 60),
    "tiktok": PlatformConfig("TikTok", 1080, 1920, 180),
    "vk_clips": PlatformConfig("VK Clips", 1080, 1920, 180),
}


@dataclass
class AppConfig:
    """Главная конфигурация"""
    # Пути
    ffmpeg_path: str = "ffmpeg"
    models_dir: Path = field(default_factory=lambda: Path("models"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))
    output_dir: Path = field(default_factory=lambda: Path("output"))

    # Whisper настройки
    whisper_model: str = "base"  # tiny, base, small, medium, large-v3
    whisper_device: str = "auto"  # auto, cpu, cuda
    whisper_compute_type: str = "auto"  # auto, int8, float16, float32

    # Vosk настройки
    vosk_model: str = "vosk-model-small-ru-0.22"
    vosk_model_en: str = "vosk-model-small-en-us-0.15"

    # Детекция хайлайтов
    min_clip_duration: float = 5.0
    max_clip_duration: float = 30.0
    audio_energy_threshold: float = 0.3
    scene_change_threshold: float = 0.4
    max_clips_per_video: int = 10

    # Аудио/музыка
    music_volume: float = 0.15  # громкость музыки под голос
    voice_volume: float = 1.0
    ducking_threshold: float = 0.1

    # Субтитры
    subtitle_font_size: int = 48
    subtitle_font_color: str = "#FFFFFF"
    subtitle_outline_color: str = "#000000"
    subtitle_outline_width: int = 2
    subtitle_position: Literal["bottom", "center", "top"] = "bottom"
    subtitle_margin_v: int = 150

    # Видео
    blur_background: bool = True
    blur_radius: int = 50
    background_opacity: float = 0.7
    smart_crop: bool = True  # центрирование по лицам/движению

    # Платформа по умолчанию
    default_platform: str = "reels"

    def __post_init__(self):
        # Создаем директории
        for dir_path in [self.models_dir, self.temp_dir, self.output_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        return {
            "ffmpeg_path": self.ffmpeg_path,
            "models_dir": str(self.models_dir),
            "temp_dir": str(self.temp_dir),
            "output_dir": str(self.output_dir),
            "whisper_model": self.whisper_model,
            "whisper_device": self.whisper_device,
            "whisper_compute_type": self.whisper_compute_type,
            "vosk_model": self.vosk_model,
            "vosk_model_en": self.vosk_model_en,
            "min_clip_duration": self.min_clip_duration,
            "max_clip_duration": self.max_clip_duration,
            "audio_energy_threshold": self.audio_energy_threshold,
            "scene_change_threshold": self.scene_change_threshold,
            "max_clips_per_video": self.max_clips_per_video,
            "music_volume": self.music_volume,
            "voice_volume": self.voice_volume,
            "ducking_threshold": self.ducking_threshold,
            "subtitle_font_size": self.subtitle_font_size,
            "subtitle_font_color": self.subtitle_font_color,
            "subtitle_outline_color": self.subtitle_outline_color,
            "subtitle_outline_width": self.subtitle_outline_width,
            "subtitle_position": self.subtitle_position,
            "subtitle_margin_v": self.subtitle_margin_v,
            "blur_background": self.blur_background,
            "blur_radius": self.blur_radius,
            "background_opacity": self.background_opacity,
            "smart_crop": self.smart_crop,
            "default_platform": self.default_platform,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        # Конвертируем строки в Path
        for key in ["models_dir", "temp_dir", "output_dir"]:
            if key in data and isinstance(data[key], str):
                data[key] = Path(data[key])
        return cls(**data)

    def save(self, path: Path):
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        if path.exists():
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        return cls()


# Глобальный экземпляр конфига
CONFIG = AppConfig.load(Path("config.json"))