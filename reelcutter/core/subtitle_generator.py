"""Генерация субтитров через faster-whisper и Vosk"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass

from .config import CONFIG

logger = logging.getLogger(__name__)


@dataclass
class SubtitleSegment:
    """Сегмент субтитров"""
    start: float
    end: float
    text: str
    language: str = "auto"


class SubtitleGenerator:
    """Обертка над faster-whisper и Vosk"""

    def __init__(self):
        self._whisper_model = None
        self._vosk_model_ru = None
        self._vosk_model_en = None

    def generate(self, video_path: str, engine: Literal["whisper", "vosk"] = "whisper",
                 language: str = "auto", translate: bool = False) -> List[SubtitleSegment]:
        """Главный метод генерации субтитров"""
        logger.info(f"Generating subtitles with {engine}...")

        if engine == "whisper":
            return self._generate_whisper(video_path, language, translate)
        elif engine == "vosk":
            return self._generate_vosk(video_path, language)
        else:
            raise ValueError(f"Unknown engine: {engine}")

    def _generate_whisper(self, video_path: str, language: str, translate: bool) -> List[SubtitleSegment]:
        """Генерация через faster-whisper"""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")

        # Ленивая загрузка модели
        if self._whisper_model is None:
            logger.info(f"Loading Whisper model: {CONFIG.whisper_model}")
            self._whisper_model = WhisperModel(
                CONFIG.whisper_model,
                device=CONFIG.whisper_device,
                compute_type=CONFIG.whisper_compute_type,
                download_root=str(CONFIG.models_dir / "whisper")
            )

        # Транскрибация
        segments, info = self._whisper_model.transcribe(
            video_path,
            language=None if language == "auto" else language,
            task="translate" if translate else "transcribe",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            word_timestamps=True,
            beam_size=5,
        )

        result = []
        for seg in segments:
            result.append(SubtitleSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                language=info.language
            ))

        logger.info(f"Whisper: {len(result)} segments, language: {info.language}")
        return result

    def _generate_vosk(self, video_path: str, language: str) -> List[SubtitleSegment]:
        """Генерация через Vosk (очень быстро, но менее точно)"""
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            import wave
            import ffmpeg
        except ImportError:
            raise RuntimeError("Vosk not installed. Run: pip install vosk")

        SetLogLevel(-1)  # Отключаем логи Vosk

        # Выбираем модель
        model_name = CONFIG.vosk_model if language in ("auto", "ru") else CONFIG.vosk_model_en
        model_path = CONFIG.models_dir / "vosk" / model_name

        if not model_path.exists():
            raise FileNotFoundError(
                f"Vosk model not found: {model_path}\n"
                f"Download from https://alphacephei.com/vosk/models and place in models/vosk/"
            )

        if language in ("auto", "ru") and self._vosk_model_ru is None:
            logger.info(f"Loading Vosk model: {model_name}")
            self._vosk_model_ru = Model(str(model_path))
            model = self._vosk_model_ru
        elif language == "en" and self._vosk_model_en is None:
            logger.info(f"Loading Vosk model: {model_name}")
            self._vosk_model_en = Model(str(model_path))
            model = self._vosk_model_en
        else:
            model = self._vosk_model_ru or self._vosk_model_en

        # Извлекаем аудио во временный WAV
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        try:
            (
                ffmpeg
                .input(video_path)
                .output(wav_path, ac=1, ar=16000, format='wav')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Распознаем
            wf = wave.open(wav_path, "rb")
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True)

            result = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    if res.get("text"):
                        # Vosk дает только финальные результаты, нужно парсить слова для таймингов
                        if "result" in res:
                            for word in res["result"]:
                                result.append(SubtitleSegment(
                                    start=word["start"],
                                    end=word["end"],
                                    text=word["word"],
                                    language=language if language != "auto" else "ru"
                                ))

            # Финальный результат
            res = json.loads(rec.FinalResult())
            if "result" in res:
                for word in res["result"]:
                    result.append(SubtitleSegment(
                        start=word["start"],
                        end=word["end"],
                        text=word["word"],
                        language=language if language != "auto" else "ru"
                    ))

            # Объединяем слова в фразы
            result = self._merge_words_to_phrases(result)

            logger.info(f"Vosk: {len(result)} segments")
            return result

        finally:
            Path(wav_path).unlink(missing_ok=True)

    def _merge_words_to_phrases(self, words: List[SubtitleSegment],
                                 max_gap: float = 0.5,
                                 max_duration: float = 5.0) -> List[SubtitleSegment]:
        """Объединение слов в фразы по паузам"""
        if not words:
            return []

        phrases = []
        current = words[0]

        for word in words[1:]:
            gap = word.start - current.end

            if gap > max_gap or (word.end - current.start) > max_duration:
                phrases.append(current)
                current = word
            else:
                current = SubtitleSegment(
                    start=current.start,
                    end=word.end,
                    text=current.text + " " + word.text,
                    language=current.language
                )

        phrases.append(current)
        return phrases

    def save_srt(self, segments: List[SubtitleSegment], output_path: Path):
        """Сохранение в SRT формат"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{self._format_time(seg.start)} --> {self._format_time(seg.end)}\n")
                f.write(f"{seg.text}\n\n")

    def save_ass(self, segments: List[SubtitleSegment], output_path: Path,
                 style: Optional[dict] = None):
        """Сохранение в ASS формат (для красивых стилей)"""
        style = style or {
            "fontsize": CONFIG.subtitle_font_size,
            "primarycolor": CONFIG.subtitle_font_color.replace("#", "&H") + "&",
            "outlinecolor": CONFIG.subtitle_outline_color.replace("#", "&H") + "&",
            "outline": CONFIG.subtitle_outline_width,
            "marginv": CONFIG.subtitle_margin_v,
            "alignment": 2 if CONFIG.subtitle_position == "bottom" else
                         5 if CONFIG.subtitle_position == "center" else 8,
        }

        header = f"""[Script Info]
Title: ReelCutter Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{style['fontsize']},{style['primarycolor']},&H000000FF,{style['outlinecolor']},&H80000000,-1,0,0,0,100,100,0,0,1,{style['outline']},0,{style['alignment']},20,20,{style['marginv']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(header)
            for seg in segments:
                start = self._format_time_ass(seg.start)
                end = self._format_time_ass(seg.end)
                text = seg.text.replace('\n', '\\N')
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

    def _format_time(self, seconds: float) -> str:
        """SRT формат времени: HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_time_ass(self, seconds: float) -> str:
        """ASS формат времени: H:MM:SS.cc"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"


def generate_subtitles(video_path: str, engine: str = "whisper",
                       language: str = "auto", translate: bool = False) -> List[SubtitleSegment]:
    """Удобная функция для генерации субтитров"""
    generator = SubtitleGenerator()
    return generator.generate(video_path, engine, language, translate)