"""Детектор залипательных моментов в видео"""
import cv2
import numpy as np
import librosa
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
import logging
from tqdm import tqdm

from .config import CONFIG

logger = logging.getLogger(__name__)


@dataclass
class HighlightSegment:
    """Сегмент-хайлайт"""
    start: float
    end: float
    score: float
    reasons: List[str]
    audio_energy: float = 0.0
    visual_activity: float = 0.0
    subtitle_score: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    def __lt__(self, other):
        return self.score > other.score  # для сортировки по убыванию


class HighlightDetector:
    """Комбинированный детектор хайлайтов: аудио + визуал + субтитры"""

    def __init__(self, video_path: str, subtitle_segments: Optional[List[dict]] = None):
        self.video_path = video_path
        self.subtitle_segments = subtitle_segments or []
        self.duration = 0.0
        self.fps = 30.0
        self._analyze_video_properties()

    def _analyze_video_properties(self):
        """Получить базовые свойства видео"""
        cap = cv2.VideoCapture(self.video_path)
        if cap.isOpened():
            self.fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration = frame_count / self.fps if self.fps > 0 else 0
        cap.release()
        logger.info(f"Video: {self.duration:.1f}s, {self.fps:.1f}fps")

    def detect(self) -> List[HighlightSegment]:
        """Главный метод детекции хайлайтов"""
        logger.info("Starting highlight detection...")

        # 1. Анализ аудио
        audio_segments = self._analyze_audio()

        # 2. Анализ визуала (смены сцен, движение, лица)
        visual_segments = self._analyze_visual()

        # 3. Анализ субтитров (ключевые фразы)
        subtitle_segments = self._analyze_subtitles()

        # 4. Комбинируем и ранжируем
        highlights = self._combine_scores(audio_segments, visual_segments, subtitle_segments)

        # 5. Фильтруем и объединяем близкие сегменты
        highlights = self._post_process(highlights)

        logger.info(f"Found {len(highlights)} highlights")
        return highlights

    def _analyze_audio(self) -> List[HighlightSegment]:
        """Анализ аудио: пики энергии, темп, речь"""
        logger.info("Analyzing audio...")
        segments = []

        try:
            # Загружаем аудио через librosa
            y, sr = librosa.load(self.video_path, sr=22050)

            # RMS энергия по окнам
            frame_length = int(sr * 1.0)  # 1 секунда
            hop_length = int(sr * 0.5)    # 0.5 секунды перекрытие

            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

            # Находим пики энергии
            from scipy.signal import find_peaks
            peaks, properties = find_peaks(
                rms,
                height=np.percentile(rms, 70),
                distance=sr // hop_length * 3  # минимум 3 сек между пиками
            )

            # Создаем сегменты вокруг пиков
            for peak_idx in peaks:
                peak_time = times[peak_idx]
                start = max(0, peak_time - CONFIG.min_clip_duration / 2)
                end = min(self.duration, peak_time + CONFIG.min_clip_duration / 2)

                # Расширяем до речевых пауз если возможно
                start, end = self._expand_to_speech_boundaries(y, sr, start, end)

                if end - start >= CONFIG.min_clip_duration:
                    segments.append(HighlightSegment(
                        start=start,
                        end=end,
                        score=float(rms[peak_idx]),
                        reasons=["audio_peak"],
                        audio_energy=float(rms[peak_idx])
                    ))

        except Exception as e:
            logger.warning(f"Audio analysis failed: {e}")

        return segments

    def _expand_to_speech_boundaries(self, y: np.ndarray, sr: int,
                                      start: float, end: float) -> tuple:
        """Расширить сегмент до границ речевой активности"""
        # Простая VAD через энергию
        frame_length = int(sr * 0.1)
        hop_length = int(sr * 0.05)

        start_sample = int(start * sr)
        end_sample = int(end * sr)

        # Ищем назад от start
        for i in range(start_sample, max(0, start_sample - int(2 * sr)), -frame_length):
            chunk = y[max(0, i - frame_length):i]
            if len(chunk) > 0 and np.sqrt(np.mean(chunk**2)) > 0.01:
                start = i / sr
            else:
                break

        # Ищем вперед от end
        for i in range(end_sample, min(len(y), end_sample + int(2 * sr)), frame_length):
            chunk = y[i:min(len(y), i + frame_length)]
            if len(chunk) > 0 and np.sqrt(np.mean(chunk**2)) > 0.01:
                end = min(self.duration, (i + frame_length) / sr)
            else:
                break

        return start, end

    def _analyze_visual(self) -> List[HighlightSegment]:
        """Анализ визуала: смена сцен, движение, детекция лиц"""
        logger.info("Analyzing visual content...")
        segments = []

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return segments

        # Детектор лиц (OpenCV 5 убрал Haar каскады — деградируем безопасно)
        face_cascade = None
        try:
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
        except Exception:
            face_cascade = None

        prev_frame = None
        scene_changes = []
        face_frames = []
        motion_scores = []

        frame_idx = 0
        sample_every = max(1, int(self.fps / 2))  # анализируем 2 кадра в сек

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        with tqdm(total=total_frames // sample_every, desc="Visual analysis") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_every == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.resize(gray, (320, 180))

                    # 1. Детекция смены сцены (гистограммы)
                    if prev_frame is not None:
                        diff = cv2.absdiff(gray, prev_frame)
                        hist_diff = np.sum(diff) / (320 * 180 * 255)
                        if hist_diff > CONFIG.scene_change_threshold:
                            scene_changes.append(frame_idx / self.fps)

                    # 2. Детекция лиц
                    if face_cascade is not None:
                        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                        if len(faces) > 0:
                            face_frames.append(frame_idx / self.fps)

                    # 3. Оптический поток (движение)
                    if prev_frame is not None:
                        flow = cv2.calcOpticalFlowFarneback(
                            prev_frame, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                        )
                        magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                        motion_scores.append((frame_idx / self.fps, np.mean(magnitude)))

                    prev_frame = gray
                    pbar.update(1)

                frame_idx += 1

        cap.release()

        # Создаем сегменты из визуальных признаков
        all_times = sorted(set(scene_changes + face_frames))

        for t in all_times:
            start = max(0, t - CONFIG.min_clip_duration / 2)
            end = min(self.duration, t + CONFIG.min_clip_duration / 2)

            # Считаем скор
            visual_score = 0.0
            reasons = []

            # Близость к смене сцены
            for sc in scene_changes:
                if abs(sc - t) < 2.0:
                    visual_score += 0.5
                    reasons.append("scene_change")

            # Близость к лицу
            for ff in face_frames:
                if abs(ff - t) < 2.0:
                    visual_score += 0.5
                    reasons.append("face_detected")

            # Движение
            for mt, ms in motion_scores:
                if abs(mt - t) < 1.0 and ms > 2.0:
                    visual_score += min(ms / 10, 0.5)
                    reasons.append("high_motion")

            if visual_score > 0 and end - start >= CONFIG.min_clip_duration:
                segments.append(HighlightSegment(
                    start=start,
                    end=end,
                    score=visual_score,
                    reasons=reasons,
                    visual_activity=visual_score
                ))

        return segments

    def _analyze_subtitles(self) -> List[HighlightSegment]:
        """Анализ субтитров: поиск ключевых фраз, эмоциональных слов"""
        if not self.subtitle_segments:
            return []

        logger.info("Analyzing subtitles...")
        segments = []

        # Ключевые слова для вирусного контента (RU + EN)
        viral_keywords = {
            'ru': [
                'невероятно', 'шок', 'не могу поверить', 'вау', 'омг', 'бля', 'да ну',
                'серьезно', 'правда', 'обман', 'секрет', 'никто не знает', 'покажу',
                'смотрите', 'внимание', 'важно', 'эксклюзив', 'раскрытие', 'провал',
                'успех', 'миллион', 'бесплатно', 'в подарок', 'лайфхак', 'трюк',
                'магия', 'чудо', 'кошмар', 'страшно', 'смешно', 'ржач', 'лол',
                'кринж', 'краш', 'влюбился', 'разбитое сердце', 'предательство',
                'смерть', 'жизнь', 'смысл', 'депрессия', 'тревога', 'паника'
            ],
            'en': [
                'unbelievable', 'shocking', 'can\'t believe', 'wow', 'omg', 'wtf',
                'seriously', 'secret', 'nobody knows', 'watch this', 'attention',
                'important', 'exclusive', 'revealed', 'fail', 'success', 'million',
                'free', 'giveaway', 'lifehack', 'trick', 'magic', 'miracle',
                'nightmare', 'scary', 'funny', 'lol', 'cringe', 'crush',
                'heartbreak', 'betrayal', 'death', 'life', 'meaning', 'depression',
                'anxiety', 'panic', 'mind blown', 'game changer'
            ]
        }

        # Эмоциональные маркеры
        emotion_markers = ['!', '?', '...', '!!!', '???', '😱', '😂', '😭', '🔥', '💀', '❤️']

        for seg in self.subtitle_segments:
            text = seg.get('text', '').lower()
            start = seg.get('start', 0)
            end = seg.get('end', 0)

            score = 0.0
            reasons = []

            # Проверка ключевых слов
            for lang, keywords in viral_keywords.items():
                for kw in keywords:
                    if kw in text:
                        score += 0.3
                        reasons.append(f"keyword:{kw}")

            # Эмоциональные маркеры
            for em in emotion_markers:
                if em in text:
                    score += 0.2
                    reasons.append("emotion_marker")

            # Длина фразы (короткие поговорки лучше)
            words = text.split()
            if 3 <= len(words) <= 15:
                score += 0.1
                reasons.append("good_length")

            # Вопросительные/повелительные
            if text.strip().endswith(('?', '!')):
                score += 0.15
                reasons.append("question_or_exclamation")

            if score > 0.2:
                # Расширяем до минимальной длительности
                dur = end - start
                if dur < CONFIG.min_clip_duration:
                    pad = (CONFIG.min_clip_duration - dur) / 2
                    start = max(0, start - pad)
                    end = min(self.duration, end + pad)

                segments.append(HighlightSegment(
                    start=start,
                    end=end,
                    score=min(score, 1.0),
                    reasons=reasons,
                    subtitle_score=score
                ))

        return segments

    def _combine_scores(self, audio_segs: List[HighlightSegment],
                        visual_segs: List[HighlightSegment],
                        subtitle_segs: List[HighlightSegment]) -> List[HighlightSegment]:
        """Комбинирование скоров из всех источников"""
        all_segments = audio_segs + visual_segs + subtitle_segs

        if not all_segments:
            return []

        # Объединяем пересекающиеся сегменты
        merged = self._merge_overlapping(all_segments)

        # Нормализуем скоры
        for seg in merged:
            # Веса: аудио 0.3, визуал 0.3, субтитры 0.4
            seg.score = (
                seg.audio_energy * 0.3 +
                seg.visual_activity * 0.3 +
                seg.subtitle_score * 0.4
            )

        # Сортируем по скору
        merged.sort()

        return merged[:CONFIG.max_clips_per_video * 2]  # берем с запасом

    def _merge_overlapping(self, segments: List[HighlightSegment],
                           iou_threshold: float = 0.3) -> List[HighlightSegment]:
        """Объединение пересекающихся сегментов"""
        if not segments:
            return []

        # Сортируем по старту
        segments.sort(key=lambda s: s.start)

        merged = []
        current = segments[0]

        for seg in segments[1:]:
            # Проверяем пересечение
            intersection = min(current.end, seg.end) - max(current.start, seg.start)
            union = max(current.end, seg.end) - min(current.start, seg.start)
            iou = intersection / union if union > 0 else 0

            if iou > iou_threshold:
                # Объединяем
                current = HighlightSegment(
                    start=min(current.start, seg.start),
                    end=max(current.end, seg.end),
                    score=max(current.score, seg.score),
                    reasons=list(set(current.reasons + seg.reasons)),
                    audio_energy=max(current.audio_energy, seg.audio_energy),
                    visual_activity=max(current.visual_activity, seg.visual_activity),
                    subtitle_score=max(current.subtitle_score, seg.subtitle_score)
                )
            else:
                merged.append(current)
                current = seg

        merged.append(current)
        return merged

    def _post_process(self, highlights: List[HighlightSegment]) -> List[HighlightSegment]:
        """Постобработка: фильтрация по длительности, дедупликация"""
        result = []

        for h in highlights:
            # Ограничиваем длительность
            if h.duration > CONFIG.max_clip_duration:
                # Обрезаем с сохранением центра
                center = (h.start + h.end) / 2
                h.start = center - CONFIG.max_clip_duration / 2
                h.end = center + CONFIG.max_clip_duration / 2
            elif h.duration < CONFIG.min_clip_duration:
                continue  # слишком короткий

            # Проверяем границы видео
            h.start = max(0, h.start)
            h.end = min(self.duration, h.end)

            if h.end - h.start >= CONFIG.min_clip_duration:
                result.append(h)

        # Финальная сортировка и лимит
        result.sort()
        return result[:CONFIG.max_clips_per_video]


def detect_highlights(video_path: str, subtitle_segments: Optional[List[dict]] = None) -> List[HighlightSegment]:
    """Удобная функция для детекции хайлайтов"""
    detector = HighlightDetector(video_path, subtitle_segments)
    return detector.detect()