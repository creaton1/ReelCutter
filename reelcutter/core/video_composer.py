"""Видео-композитор: вертикальный формат, блюр, музыка, сабы, рекламные баннеры"""
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Literal
from dataclasses import dataclass

import cv2
import numpy as np
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    ImageClip, ColorClip, TextClip, vfx, afx
)

from .config import CONFIG, PLATFORMS
from .highlight_detector import HighlightSegment

logger = logging.getLogger(__name__)


@dataclass
class AdBanner:
    """Рекламный баннер (картинка или видео)"""
    path: str
    start_time: float  # когда показать (секунды от начала клипа)
    duration: float    # сколько показывать
    position: Literal["top", "bottom", "center", "overlay"] = "overlay"
    opacity: float = 1.0
    clickable_area: Optional[tuple] = None  # (x, y, w, h) в процентах


class VideoComposer:
    """Создание вертикальных клипов с наложениями"""

    def __init__(self, platform: str = "reels"):
        self.platform = PLATFORMS.get(platform, PLATFORMS["reels"])
        self.target_w = self.platform.width
        self.target_h = self.platform.height

    def create_clips(self, video_path: str, highlights: List[HighlightSegment],
                     music_path: Optional[str] = None,
                     subtitle_segments: Optional[List] = None,
                     ad_banners: Optional[List[AdBanner]] = None,
                     output_dir: Optional[Path] = None,
                     progress_callback=None) -> List[Path]:
        """Создать клипы из хайлайтов"""
        output_dir = output_dir or CONFIG.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        total = len(highlights)

        for i, highlight in enumerate(highlights):
            if progress_callback:
                progress_callback(i / total, f"Rendering clip {i+1}/{total}: {highlight.start:.1f}s-{highlight.end:.1f}s")

            output_path = output_dir / f"clip_{i+1:03d}_{int(highlight.start)}s_{int(highlight.end)}s.mp4"

            try:
                self._create_single_clip(
                    video_path, highlight, output_path,
                    music_path, subtitle_segments, ad_banners
                )
                results.append(output_path)
                logger.info(f"Created: {output_path}")
            except Exception as e:
                logger.error(f"Failed to create clip {i+1}: {e}")
                if progress_callback:
                    progress_callback(i / total, f"Error on clip {i+1}: {e}")

        if progress_callback:
            progress_callback(1.0, f"Done! Created {len(results)} clips")

        return results

    def _create_single_clip(self, video_path: str, highlight: HighlightSegment,
                            output_path: Path, music_path: Optional[str],
                            subtitle_segments: Optional[List],
                            ad_banners: Optional[List[AdBanner]]):
        """Создание одного клипа"""
        # Загружаем исходное видео
        source = VideoFileClip(video_path).subclipped(highlight.start, highlight.end)
        source_duration = source.duration

        # 1. Приводим к вертикальному формату (9:16)
        vertical_clip = self._make_vertical(source)

        # 2. Добавляем субтитры
        if subtitle_segments:
            vertical_clip = self._add_subtitles(vertical_clip, subtitle_segments,
                                                highlight.start, highlight.end)

        # 3. Добавляем рекламные баннеры
        if ad_banners:
            vertical_clip = self._add_ad_banners(vertical_clip, ad_banners, source_duration)

        # 4. Аудио: оригинал + музыка с даккингом
        final_audio = self._compose_audio(source, music_path, source_duration)
        vertical_clip = vertical_clip.with_audio(final_audio)

        # 5. Экспорт
        vertical_clip.write_videofile(
            str(output_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            bitrate="5000k",
            audio_bitrate="128k",
            preset="medium",
            threads=4,
            logger=None
        )

        # Очистка
        source.close()
        vertical_clip.close()
        if final_audio:
            final_audio.close()

    def _make_vertical(self, clip: VideoFileClip) -> VideoFileClip:
        """Превращаем горизонтальное видео в вертикальное 9:16"""
        w, h = clip.size
        target_ratio = self.target_w / self.target_h
        source_ratio = w / h

        if abs(source_ratio - target_ratio) < 0.05:
            # Уже правильное соотношение
            return clip.resized((self.target_w, self.target_h))

        if CONFIG.smart_crop:
            # Умный кроп: пытаемся оставить лица/действие в центре
            return self._smart_crop_vertical(clip)
        else:
            # Простой кроп по центру или блюр-бэкграунд
            if CONFIG.blur_background:
                return self._blur_background_vertical(clip)
            else:
                return self._center_crop_vertical(clip)

    def _smart_crop_vertical(self, clip: VideoFileClip) -> VideoFileClip:
        """Умный вертикальный кроп с детекцией лиц"""
        # Анализируем несколько кадров для поиска зоны интереса
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        sample_times = np.linspace(0, clip.duration, min(10, int(clip.duration)))
        face_regions = []

        for t in sample_times:
            frame = clip.get_frame(t)
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            for (x, y, fw, fh) in faces:
                # Центр лица в относительных координатах
                cx = (x + fw/2) / frame.shape[1]
                cy = (y + fh/2) / frame.shape[0]
                face_regions.append((cx, cy))

        if face_regions:
            # Средний центр лиц
            avg_cx = np.mean([r[0] for r in face_regions])
            avg_cy = np.mean([r[1] for r in face_regions])
        else:
            avg_cx, avg_cy = 0.5, 0.5  # центр

        # Кроп с учетом найденного центра
        w, h = clip.size
        target_w = int(h * self.target_w / self.target_h)

        if target_w <= w:
            # Исходное шире нужного - кропим по горизонтали
            x_center = int(avg_cx * w)
            x1 = max(0, min(w - target_w, x_center - target_w // 2))
            cropped = clip.cropped(x1=x1, x2=x1 + target_w)
        else:
            # Исходное уже узкое - растягиваем или добавляем блюр
            return self._blur_background_vertical(clip)

        return cropped.resized((self.target_w, self.target_h))

    def _blur_background_vertical(self, clip: VideoFileClip) -> VideoFileClip:
        """Вертикальное видео с размытым фоном (блюр-бэкграунд)"""
        w, h = clip.size
        target_ratio = self.target_w / self.target_h

        # Масштабируем исходник под высоту
        scaled_h = self.target_h
        scaled_w = int(h * self.target_w / self.target_h * (w / h) / target_ratio)

        # Если исходник шире - вписываем по ширине с блюром по бокам
        if w / h > target_ratio:
            # Исходник шире - кропим по центру, блюр не нужен
            return self._center_crop_vertical(clip)
        else:
            # Исходник уже/выше - создаем блюр фон
            # 1. Основное видео в центре
            main_clip = clip.resized(height=self.target_h)
            main_w = main_clip.size[0]
            x_pos = (self.target_w - main_w) // 2

            # 2. Блюр фон из того же видео (увеличенный и размытый)
            bg_clip = clip.resized(width=self.target_w * 2)
            # Применяем блюр через image_transform
            bg_clip = bg_clip.image_transform(self._blur_frame)

            # 3. Композиция
            from moviepy import CompositeVideoClip
            final = CompositeVideoClip([
                bg_clip.with_position("center"),
                main_clip.with_position((x_pos, 0)).with_opacity(1.0)
            ], size=(self.target_w, self.target_h))

            return final.with_duration(clip.duration)

    def _center_crop_vertical(self, clip: VideoFileClip) -> VideoFileClip:
        """Простой центрированный кроп"""
        w, h = clip.size
        target_ratio = self.target_w / self.target_h

        if w / h > target_ratio:
            # Шире - кропим по бокам
            new_w = int(h * target_ratio)
            x1 = (w - new_w) // 2
            return clip.cropped(x1=x1, x2=x1 + new_w).resized((self.target_w, self.target_h))
        else:
            # Выше - кропим сверху/снизу
            new_h = int(w / target_ratio)
            y1 = (h - new_h) // 2
            return clip.cropped(y1=y1, y2=y1 + new_h).resized((self.target_w, self.target_h))

    def _blur_frame(self, frame: np.ndarray) -> np.ndarray:
        """Размытие кадра для блюр-фона"""
        return cv2.GaussianBlur(frame, (51, 51), CONFIG.blur_radius)

    def _add_subtitles(self, clip: VideoFileClip, subtitle_segments: List,
                       clip_start: float, clip_end: float) -> VideoFileClip:
        """Наложение субтитров"""
        # Фильтруем субтитры для этого клипа
        relevant = [
            s for s in subtitle_segments
            if s.end > clip_start and s.start < clip_end
        ]

        if not relevant:
            return clip

        # Создаем ASS файл для красивых субтитров
        from .subtitle_generator import SubtitleGenerator
        gen = SubtitleGenerator()

        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode='w', encoding='utf-8') as f:
            ass_path = f.name
            gen.save_ass(relevant, Path(ass_path))

        # Накладываем субтитры через ffmpeg (лучше качеством)
        # Для простоты используем TextClip (но ASS лучше)
        subtitle_clips = []
        for seg in relevant:
            rel_start = seg.start - clip_start
            rel_end = seg.end - clip_start
            if rel_end <= 0 or rel_start >= clip.duration:
                continue

            txt_clip = TextClip(
                text=seg.text,
                font_size=CONFIG.subtitle_font_size,
                color=CONFIG.subtitle_font_color,
                stroke_color=CONFIG.subtitle_outline_color,
                stroke_width=CONFIG.subtitle_outline_width,
                method="caption",
                size=(self.target_w - 80, None),
                font="Arial"
            ).with_duration(rel_end - rel_start).with_start(max(0, rel_start))

            # Позиционирование
            if CONFIG.subtitle_position == "bottom":
                txt_clip = txt_clip.with_position(("center", self.target_h - CONFIG.subtitle_margin_v))
            elif CONFIG.subtitle_position == "top":
                txt_clip = txt_clip.with_position(("center", CONFIG.subtitle_margin_v))
            else:
                txt_clip = txt_clip.with_position(("center", "center"))

            subtitle_clips.append(txt_clip)

        if subtitle_clips:
            from moviepy import CompositeVideoClip
            clip = CompositeVideoClip([clip] + subtitle_clips, size=clip.size)

        return clip

    def _add_ad_banners(self, clip: VideoFileClip, ad_banners: List[AdBanner],
                        clip_duration: float) -> VideoFileClip:
        """Добавление рекламных баннеров (картинки и видео)"""
        overlay_clips = []

        for banner in ad_banners:
            # Проверяем, попадает ли баннер в длительность клипа
            if banner.start_time >= clip_duration:
                continue

            banner_end = min(banner.start_time + banner.duration, clip_duration)
            banner_dur = banner_end - banner.start_time
            if banner_dur <= 0:
                continue

            try:
                if banner.path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                    # Видеобаннер
                    banner_clip = VideoFileClip(banner.path)
                    # Зацикливаем или обрезаем
                    if banner_clip.duration < banner_dur:
                        # Зацикливаем через конкатенацию
                        loops = int(banner_dur / banner_clip.duration) + 1
                        from moviepy import concatenate_videoclips
                        banner_clip = concatenate_videoclips([banner_clip] * loops).subclipped(0, banner_dur)
                    else:
                        banner_clip = banner_clip.subclipped(0, banner_dur)

                    # Ресайз под экран или оверлей
                    if banner.position == "overlay":
                        # Небольшой оверлей в углу
                        banner_clip = banner_clip.resized(height=self.target_h // 4)
                        pos = ("right", "bottom")
                    else:
                        # На весь экран
                        banner_clip = banner_clip.resized((self.target_w, self.target_h))
                        pos = "center"

                else:
                    # Картинка
                    from moviepy import ImageClip
                    banner_clip = ImageClip(banner.path).with_duration(banner_dur)

                    if banner.position == "overlay":
                        banner_clip = banner_clip.resized(height=self.target_h // 4)
                        pos = ("right", "bottom")
                    else:
                        banner_clip = banner_clip.resized((self.target_w, self.target_h))
                        pos = "center"

                # Прозрачность
                if banner.opacity < 1.0:
                    banner_clip = banner_clip.with_opacity(banner.opacity)

                # Позиция и время
                banner_clip = banner_clip.with_start(banner.start_time).with_position(pos)
                overlay_clips.append(banner_clip)

            except Exception as e:
                logger.warning(f"Failed to load banner {banner.path}: {e}")

        if overlay_clips:
            from moviepy import CompositeVideoClip
            clip = CompositeVideoClip([clip] + overlay_clips, size=clip.size)

        return clip

    def _compose_audio(self, source_clip: VideoFileClip, music_path: Optional[str],
                       duration: float) -> Optional[CompositeAudioClip]:
        """Композиция аудио: голос + музыка с даккингом"""
        audio_clips = []

        # Оригинальный звук
        if source_clip.audio:
            orig_audio = source_clip.audio.with_volume_scaled(CONFIG.voice_volume)
            audio_clips.append(orig_audio)

        # Музыка
        if music_path and Path(music_path).exists():
            music = AudioFileClip(music_path)

            # Зацикливаем музыку если короче
            if music.duration < duration:
                # Простое зацикливание через конкатенацию
                loops = int(duration / music.duration) + 1
                from moviepy import concatenate_audioclips
                music = concatenate_audioclips([music] * loops).subclipped(0, duration)
            else:
                music = music.subclipped(0, duration)

            # Даккинг: приглушаем музыку когда есть речь
            music = music.with_volume_scaled(CONFIG.music_volume)
            audio_clips.append(music)

        if not audio_clips:
            return None

        if len(audio_clips) == 1:
            return audio_clips[0]

        return CompositeAudioClip(audio_clips)


def create_clips(video_path: str, highlights: List[HighlightSegment],
                 platform: str = "reels", music_path: Optional[str] = None,
                 subtitle_segments: Optional[List] = None,
                 ad_banners: Optional[List[AdBanner]] = None,
                 output_dir: Optional[Path] = None,
                 progress_callback=None) -> List[Path]:
    """Удобная функция для создания клипов"""
    composer = VideoComposer(platform)
    return composer.create_clips(
        video_path, highlights, music_path, subtitle_segments,
        ad_banners, output_dir, progress_callback
    )