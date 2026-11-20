"""Главное окно приложения ReelCutter на CustomTkinter с видео-превью"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import threading
import logging
import queue
import time
from typing import Optional, List, Callable

import cv2
from PIL import Image, ImageTk

from ..core.config import CONFIG, PLATFORMS
from ..core.highlight_detector import HighlightSegment, detect_highlights
from ..core.subtitle_generator import SubtitleGenerator, SubtitleSegment, generate_subtitles
from ..core.video_composer import VideoComposer, AdBanner, create_clips

# Настройка темы
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Акцентные цвета
COLOR_ACCENT = "#4CC9F0"
COLOR_SUCCESS = "#00F260"
COLOR_WARNING = "#FFA500"
COLOR_ERROR = "#FF4D4D"
COLOR_BG = "#0F0F12"
COLOR_CARD = "#1A1A1E"
COLOR_TEXT = "#E0E0E0"
COLOR_TEXT_DIM = "#888888"

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """Хендлер для вывода логов в UI"""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class VideoPreview(ctk.CTkFrame):
    """Виджет видео-превью с воспроизведением и таймлайном"""

    def __init__(self, parent, width: int = 640, height: int = 360, **kwargs):
        super().__init__(parent, **kwargs)
        self.width = width
        self.height = height
        self.video_path: Optional[Path] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.fps = 30
        self.total_frames = 0
        self.duration = 0.0
        self.current_frame = 0
        self.current_time = 0.0
        self.is_playing = False
        self.is_loaded = False
        self._play_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Заголовок
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=40)
        self.header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)

        self.video_label = ctk.CTkLabel(
            self.header,
            text="🎬 Видео не загружено",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_DIM,
        )
        self.video_label.grid(row=0, column=0, sticky="w")

        self.time_label = ctk.CTkLabel(
            self.header,
            text="00:00 / 00:00",
            font=ctk.CTkFont(size=12, family="Consolas"),
            text_color=COLOR_TEXT_DIM,
        )
        self.time_label.grid(row=0, column=1, sticky="e")

        # Canvas для видео
        self.canvas = tk.Canvas(
            self,
            width=self.width,
            height=self.height,
            bg="#000000",
            highlightthickness=0,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # Контролы воспроизведения
        self.controls = ctk.CTkFrame(self, fg_color="transparent", height=60)
        self.controls.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.controls.grid_propagate(False)
        self.controls.grid_columnconfigure(1, weight=1)

        self.btn_play = ctk.CTkButton(
            self.controls,
            text="▶",
            width=40,
            height=36,
            command=self._toggle_play,
            state="disabled",
            fg_color=COLOR_ACCENT,
            hover_color="#38B2AC",
        )
        self.btn_play.grid(row=0, column=0, padx=(0, 10))

        self.btn_load = ctk.CTkButton(
            self.controls,
            text="📂 Загрузить",
            width=100,
            height=36,
            command=self._on_load_clicked,
        )
        self.btn_load.grid(row=0, column=1, sticky="w")

        # Таймлайн
        self.timeline_var = ctk.DoubleVar(value=0)
        self.timeline = ctk.CTkSlider(
            self.controls,
            from_=0,
            to=100,
            variable=self.timeline_var,
            command=self._on_seek,
            width=300,
        )
        self.timeline.grid(row=0, column=2, sticky="ew", padx=10)

        # Настройка весов для растяжения таймлайна
        self.controls.grid_columnconfigure(2, weight=1)

    def _on_load_clicked(self):
        """Обработчик клика на загрузку видео из превью"""
        self.event_generate("<<LoadVideo>>")

    def load_video(self, video_path: str | Path):
        """Загружает видео для превью"""
        self.unload_video()
        self.video_path = Path(video_path)
        self.cap = cv2.VideoCapture(str(self.video_path))

        if not self.cap.isOpened():
            logger.error(f"Не удалось открыть видео: {self.video_path}")
            self.video_label.configure(text="❌ Ошибка загрузки видео", text_color=COLOR_ERROR)
            return

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0

        self.is_loaded = True
        self.current_frame = 0
        self.current_time = 0.0

        # Обновляем UI
        name = self.video_path.name
        if len(name) > 40:
            name = name[:37] + "..."
        self.video_label.configure(text=f"🎬 {name}", text_color=COLOR_SUCCESS)
        self.btn_play.configure(state="normal")
        self.timeline.configure(to=self.duration)
        self._update_time_label()
        self._show_frame(0)

        logger.info(f"Видео загружено в превью: {self.video_path.name} ({self.duration:.1f}s)")

    def unload_video(self):
        """Выгружает видео"""
        self.stop_playback()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.video_path = None
        self.is_loaded = False
        self.current_frame = 0
        self.current_time = 0.0
        self.total_frames = 0
        self.duration = 0.0
        self.video_label.configure(text="🎬 Видео не загружено", text_color=COLOR_TEXT_DIM)
        self.time_label.configure(text="00:00 / 00:00")
        self.btn_play.configure(state="disabled", text="▶")
        self.timeline.configure(to=100)
        self.timeline_var.set(0)
        self.canvas.delete("all")

    def _show_frame(self, frame_index: int):
        """Отображает кадр по индексу"""
        if not self.is_loaded or not self.cap:
            return

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        if not ret:
            return

        # Конвертируем BGR -> RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)

        # Масштабируем под canvas с сохранением пропорций
        canvas_w = self.canvas.winfo_width() or self.width
        canvas_h = self.canvas.winfo_height() or self.height
        img_w, img_h = img.size
        scale = min(canvas_w / img_w, canvas_h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(
            canvas_w // 2, canvas_h // 2,
            image=photo,
            anchor=tk.CENTER,
        )
        self.canvas.image = photo  # держим ссылку

        self.current_frame = frame_index
        self.current_time = frame_index / self.fps if self.fps > 0 else 0
        self._update_time_label()

        # Обновляем таймлайн без триггера команды
        self.timeline_var.set(self.current_time)

    def _update_time_label(self):
        """Обновляет надпись времени"""
        cur = self._format_time(self.current_time)
        total = self._format_time(self.duration)
        self.time_label.configure(text=f"{cur} / {total}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _toggle_play(self):
        """Включает/выключает воспроизведение"""
        if not self.is_loaded:
            return
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        """Запускает воспроизведение"""
        if not self.is_loaded or self.is_playing:
            return
        self.is_playing = True
        self.btn_play.configure(text="⏸", fg_color=COLOR_WARNING)
        self._stop_event.clear()
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()

    def stop_playback(self):
        """Останавливает воспроизведение"""
        self.is_playing = False
        self.btn_play.configure(text="▶", fg_color=COLOR_ACCENT)
        self._stop_event.set()

    def _play_loop(self):
        """Цикл воспроизведения в отдельном потоке"""
        while self.is_playing and not self._stop_event.is_set():
            if self.current_frame >= self.total_frames - 1:
                self.stop_playback()
                break
            next_frame = self.current_frame + 1
            self.after(0, self._show_frame, next_frame)
            time.sleep(1 / self.fps)

    def _on_seek(self, value):
        """Обработка перемотки таймлайна"""
        if not self.is_loaded:
            return
        self.stop_playback()
        frame_index = int(float(value) * self.fps)
        frame_index = max(0, min(frame_index, self.total_frames - 1))
        self._show_frame(frame_index)

    def add_highlight_markers(self, highlights: List[HighlightSegment]):
        """Добавляет маркеры хайлайтов на таймлайн"""
        # В текущей реализации CTkSlider не поддерживает кастомные маркеры,
        # поэтому просто отрисовываем их на canvas как оверлей (опционально)
        pass

    def destroy(self):
        self.stop_playback()
        if self.cap:
            self.cap.release()
        super().destroy()


class ReelCutterApp(ctk.CTk):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        self.title("ReelCutter — Авто-клипы для Reels / Shorts / TikTok")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self.configure(fg_color=COLOR_BG)

        # Состояние
        self.video_path: Optional[Path] = None
        self.music_path: Optional[Path] = None
        self.subtitle_segments: List[SubtitleSegment] = []
        self.highlights: List[HighlightSegment] = []
        self.ad_banners: List[AdBanner] = []
        self.processing = False
        self.log_queue = queue.Queue()

        # Настройка логирования в UI
        self._setup_logging()

        # Построение UI
        self._build_ui()

        # Запуск обработки логов
        self._process_log_queue()

    def _setup_logging(self):
        """Настройка логирования"""
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        for h in logger.handlers[:]:
            logger.removeHandler(h)

        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console)

        ui_handler = LogHandler(self.log_queue)
        ui_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        logger.addHandler(ui_handler)

    def _build_ui(self):
        """Построение интерфейса"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Верхняя панель - загрузка медиа
        self._build_top_panel()

        # Центральная область - превью слева, настройки справа
        self._build_center_area()

        # Нижняя панель - логи и прогресс
        self._build_bottom_panel()

    def _build_top_panel(self):
        """Верхняя панель: видео, музыка, баннеры"""
        top = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        top.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        top.grid_columnconfigure(1, weight=1)
        top.grid_columnconfigure(3, weight=1)

        # Видео
        ctk.CTkLabel(
            top, text="🎬 Видео",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=0, column=0, padx=15, pady=12, sticky="w")

        self.video_entry = ctk.CTkEntry(
            top,
            placeholder_text="Перетащите видеофайл или нажмите Обзор...",
            height=36,
            font=ctk.CTkFont(size=12),
        )
        self.video_entry.grid(row=0, column=1, padx=10, pady=12, sticky="ew")

        self.btn_browse_video = ctk.CTkButton(
            top, text="Обзор", width=90, height=36,
            command=self._browse_video, fg_color=COLOR_ACCENT,
            hover_color="#38B2AC",
        )
        self.btn_browse_video.grid(row=0, column=2, padx=10, pady=12)

        # Музыка
        ctk.CTkLabel(
            top, text="🎵 Музыка",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=1, column=0, padx=15, pady=12, sticky="w")

        self.music_entry = ctk.CTkEntry(
            top,
            placeholder_text="Файл музыки (опционально)",
            height=36,
            font=ctk.CTkFont(size=12),
        )
        self.music_entry.grid(row=1, column=1, padx=10, pady=12, sticky="ew")

        self.btn_browse_music = ctk.CTkButton(
            top, text="Обзор", width=90, height=36,
            command=self._browse_music,
        )
        self.btn_browse_music.grid(row=1, column=2, padx=10, pady=12)

        # Баннеры
        ctk.CTkLabel(
            top, text="📢 Баннеры",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=2, column=0, padx=15, pady=12, sticky="w")

        self.banners_frame = ctk.CTkFrame(top, fg_color="transparent")
        self.banners_frame.grid(row=2, column=1, padx=10, pady=12, sticky="ew")
        self.banners_frame.grid_columnconfigure(0, weight=1)

        self.btn_add_banner = ctk.CTkButton(
            top, text="+ Добавить", width=90, height=36,
            command=self._add_banner,
        )
        self.btn_add_banner.grid(row=2, column=2, padx=10, pady=12)

        self.banner_widgets = []

        # Кнопка быстрого запуска (если видео уже загружено)
        self.btn_quick_start = ctk.CTkButton(
            top, text="▶ Найти хайлайты", width=150, height=40,
            command=self._start_detection, state="disabled",
            fg_color=COLOR_SUCCESS, hover_color="#00C853",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.btn_quick_start.grid(row=0, column=3, rowspan=3, padx=15, pady=12, sticky="ns")

    def _build_center_area(self):
        """Центральная область: видео-превью слева, настройки и хайлайты справа"""
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        center.grid_columnconfigure(0, weight=2)  # видео-превью шире
        center.grid_columnconfigure(1, weight=1)
        center.grid_rowconfigure(0, weight=1)

        # Левая колонка - видео-превью
        self._build_video_column(center)

        # Правая колонка - настройки + хайлайты
        self._build_right_column(center)

    def _build_video_column(self, parent):
        """Колонка с видео-превью"""
        column = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12)
        column.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        column.grid_columnconfigure(0, weight=1)
        column.grid_rowconfigure(1, weight=1)

        # Заголовок колонки
        header = ctk.CTkFrame(column, fg_color="transparent", height=50)
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        header.grid_propagate(False)

        ctk.CTkLabel(
            header, text="📺 Предпросмотр видео",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        # Видео-превью
        self.video_preview = VideoPreview(column, width=700, height=394)
        self.video_preview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        # Привязка события загрузки видео из превью
        self.video_preview.bind("<<LoadVideo>>", lambda e: self._browse_video())

        # Кнопки управления видео
        video_ctrl = ctk.CTkFrame(column, fg_color="transparent")
        video_ctrl.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 15))
        video_ctrl.grid_columnconfigure(0, weight=1)

        self.btn_refresh_preview = ctk.CTkButton(
            video_ctrl, text="🔄 Обновить кадр",
            width=130, height=32,
            command=self._refresh_preview_frame,
            state="disabled",
        )
        self.btn_refresh_preview.grid(row=0, column=0, padx=5)

        self.btn_fullscreen_preview = ctk.CTkButton(
            video_ctrl, text="⛶ Расширить",
            width=130, height=32,
            command=self._toggle_fullscreen_preview,
            state="disabled",
        )
        self.btn_fullscreen_preview.grid(row=0, column=1, padx=5)

    def _build_right_column(self, parent):
        """Правая колонка: настройки + хайлайты"""
        column = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        column.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        column.grid_columnconfigure(0, weight=1)

        # --- Настройки (свернутые секции) ---
        settings_card = ctk.CTkFrame(column, fg_color=COLOR_CARD, corner_radius=12)
        settings_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        settings_card.grid_columnconfigure(0, weight=1)

        # Заголовок настроек с кнопкой свернуть
        settings_header = ctk.CTkFrame(settings_card, fg_color="transparent")
        settings_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        settings_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            settings_header, text="⚙️ Настройки",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=0, column=0, sticky="w")

        self.btn_collapse_settings = ctk.CTkButton(
            settings_header, text="▼", width=30, height=28,
            command=self._toggle_settings_collapse, fg_color="transparent",
            hover_color=COLOR_CARD, text_color=COLOR_TEXT_DIM,
        )
        self.btn_collapse_settings.grid(row=0, column=1, sticky="e")

        self.settings_content = ctk.CTkFrame(settings_card, fg_color="transparent")
        self.settings_content.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.settings_content.grid_columnconfigure(1, weight=1)

        self._build_settings_content(self.settings_content)
        self._settings_collapsed = False

        # --- Хайлайты ---
        highlights_card = ctk.CTkFrame(column, fg_color=COLOR_CARD, corner_radius=12)
        highlights_card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        highlights_card.grid_columnconfigure(0, weight=1)
        highlights_card.grid_rowconfigure(2, weight=1)

        h_header = ctk.CTkFrame(highlights_card, fg_color="transparent")
        h_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        h_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            h_header, text="🎯 Найденные хайлайты",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(h_header, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        self.detect_btn = ctk.CTkButton(
            btn_frame, text="🔍 Найти хайлайты",
            command=self._start_detection, width=150,
            fg_color=COLOR_ACCENT, hover_color="#38B2AC",
        )
        self.detect_btn.grid(row=0, column=0, padx=5)

        self.generate_btn = ctk.CTkButton(
            btn_frame, text="🎬 Создать клипы",
            command=self._start_generation, width=150,
            state="disabled",
            fg_color=COLOR_SUCCESS, hover_color="#00C853",
        )
        self.generate_btn.grid(row=0, column=1, padx=5)

        self.highlights_list = ctk.CTkScrollableFrame(highlights_card, fg_color="transparent")
        self.highlights_list.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        self.highlights_list.grid_columnconfigure(0, weight=1)

        self.preview_placeholder = ctk.CTkLabel(
            self.highlights_list,
            text="Загрузите видео и нажмите \"Найти хайлайты\"",
            text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(size=13),
        )
        self.preview_placeholder.grid(row=0, column=0, pady=60)

        self.highlight_widgets = []

    def _build_settings_content(self, parent):
        """Содержимое панели настроек"""
        row = 0

        # Платформа
        ctk.CTkLabel(
            parent, text="📱 Платформа",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=row, column=0, columnspan=2, pady=(0, 10), sticky="w")
        row += 1

        self.platform_var = ctk.StringVar(value=CONFIG.default_platform)
        platform_frame = ctk.CTkFrame(parent, fg_color="transparent")
        platform_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        for i, (key, cfg) in enumerate(PLATFORMS.items()):
            rb = ctk.CTkRadioButton(
                platform_frame, text=f"{cfg.name} ({cfg.max_duration}s)",
                variable=self.platform_var, value=key,
                fg_color=COLOR_ACCENT,
            )
            rb.grid(row=0, column=i, padx=8, sticky="w")
        row += 1

        # Длительность клипов
        ctk.CTkLabel(
            parent, text="⏱ Длительность клипов",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=row, column=0, columnspan=2, pady=(10, 10), sticky="w")
        row += 1

        dur_frame = ctk.CTkFrame(parent, fg_color="transparent")
        dur_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        dur_frame.grid_columnconfigure(1, weight=1)
        dur_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(dur_frame, text="Мин:", text_color=COLOR_TEXT).grid(row=0, column=0, padx=5)
        self.min_dur_var = ctk.DoubleVar(value=CONFIG.min_clip_duration)
        ctk.CTkSlider(dur_frame, from_=1, to=30, variable=self.min_dur_var, number_of_steps=29).grid(
            row=0, column=1, sticky="ew", padx=5
        )
        self.min_dur_label = ctk.CTkLabel(dur_frame, text=f"{CONFIG.min_clip_duration:.0f}с", text_color=COLOR_TEXT_DIM)
        self.min_dur_label.grid(row=0, column=2, padx=5)
        self.min_dur_var.trace_add("write", lambda *_: self.min_dur_label.configure(text=f"{self.min_dur_var.get():.0f}с"))

        ctk.CTkLabel(dur_frame, text="Макс:", text_color=COLOR_TEXT).grid(row=1, column=0, padx=5, pady=(8, 0))
        self.max_dur_var = ctk.DoubleVar(value=CONFIG.max_clip_duration)
        ctk.CTkSlider(dur_frame, from_=10, to=180, variable=self.max_dur_var, number_of_steps=170).grid(
            row=1, column=1, sticky="ew", padx=5, pady=(8, 0)
        )
        self.max_dur_label = ctk.CTkLabel(dur_frame, text=f"{CONFIG.max_clip_duration:.0f}с", text_color=COLOR_TEXT_DIM)
        self.max_dur_label.grid(row=1, column=2, padx=5, pady=(8, 0))
        self.max_dur_var.trace_add("write", lambda *_: self.max_dur_label.configure(text=f"{self.max_dur_var.get():.0f}с"))
        row += 1

        # Количество клипов
        ctk.CTkLabel(
            parent, text="🔢 Количество клипов",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=row, column=0, columnspan=2, pady=(10, 10), sticky="w")
        row += 1

        self.max_clips_var = ctk.IntVar(value=CONFIG.max_clips_per_video)
        clips_frame = ctk.CTkFrame(parent, fg_color="transparent")
        clips_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        clips_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkSlider(clips_frame, from_=1, to=20, variable=self.max_clips_var, number_of_steps=19).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=5
        )
        self.clips_label = ctk.CTkLabel(clips_frame, text=f"{CONFIG.max_clips_per_video}", text_color=COLOR_TEXT_DIM)
        self.clips_label.grid(row=0, column=2, padx=5)
        self.max_clips_var.trace_add("write", lambda *_: self.clips_label.configure(text=f"{self.max_clips_var.get()}"))
        row += 1

        # Субтитры
        ctk.CTkLabel(
            parent, text="💬 Субтитры",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=row, column=0, columnspan=2, pady=(10, 10), sticky="w")
        row += 1

        sub_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sub_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        sub_frame.grid_columnconfigure(1, weight=1)

        self.subtitles_enabled = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            sub_frame, text="Включить субтитры", variable=self.subtitles_enabled,
            fg_color=COLOR_ACCENT,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=3)

        ctk.CTkLabel(sub_frame, text="Движок:", text_color=COLOR_TEXT).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.sub_engine_var = ctk.StringVar(value="whisper")
        ctk.CTkOptionMenu(sub_frame, values=["whisper", "vosk"], variable=self.sub_engine_var, width=120).grid(
            row=1, column=1, padx=5, pady=5, sticky="w"
        )

        ctk.CTkLabel(sub_frame, text="Язык:", text_color=COLOR_TEXT).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.sub_lang_var = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(sub_frame, values=["auto", "ru", "en"], variable=self.sub_lang_var, width=120).grid(
            row=2, column=1, padx=5, pady=5, sticky="w"
        )

        self.translate_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            sub_frame, text="Перевести на английский", variable=self.translate_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=3)
        row += 1

        # Видео
        ctk.CTkLabel(
            parent, text="🎨 Видео",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=row, column=0, columnspan=2, pady=(10, 10), sticky="w")
        row += 1

        vid_frame = ctk.CTkFrame(parent, fg_color="transparent")
        vid_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        self.blur_bg_var = ctk.BooleanVar(value=CONFIG.blur_background)
        ctk.CTkCheckBox(vid_frame, text="Размытый фон", variable=self.blur_bg_var).grid(
            row=0, column=0, sticky="w", pady=2
        )

        self.smart_crop_var = ctk.BooleanVar(value=CONFIG.smart_crop)
        ctk.CTkCheckBox(vid_frame, text="Умный кроп (по лицам)", variable=self.smart_crop_var).grid(
            row=0, column=1, sticky="w", pady=2, padx=(20, 0)
        )
        row += 1

        # Аудио
        ctk.CTkLabel(
            parent, text="🔊 Аудио",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=row, column=0, columnspan=2, pady=(10, 10), sticky="w")
        row += 1

        aud_frame = ctk.CTkFrame(parent, fg_color="transparent")
        aud_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        aud_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(aud_frame, text="Громкость музыки:", text_color=COLOR_TEXT).grid(row=0, column=0, padx=5, sticky="w")
        self.music_vol_var = ctk.DoubleVar(value=CONFIG.music_volume)
        ctk.CTkSlider(aud_frame, from_=0, to=1, variable=self.music_vol_var, number_of_steps=100).grid(
            row=0, column=1, sticky="ew", padx=5
        )
        self.music_vol_label = ctk.CTkLabel(aud_frame, text=f"{int(CONFIG.music_volume*100)}%", text_color=COLOR_TEXT_DIM)
        self.music_vol_label.grid(row=0, column=2, padx=5)
        self.music_vol_var.trace_add("write", lambda *_: self.music_vol_label.configure(text=f"{int(self.music_vol_var.get()*100)}%"))

    def _toggle_settings_collapse(self):
        """Сворачивает/разворачивает панель настроек"""
        if self._settings_collapsed:
            self.settings_content.grid()
            self.btn_collapse_settings.configure(text="▼")
            self._settings_collapsed = False
        else:
            self.settings_content.grid_remove()
            self.btn_collapse_settings.configure(text="▲")
            self._settings_collapsed = True

    def _build_bottom_panel(self):
        """Нижняя панель: прогресс и логи"""
        bottom = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        bottom.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, weight=1)
        bottom.grid_propagate(False)

        # Прогресс
        self.progress_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        self.progress_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 5))
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, variable=self.progress_var, height=16)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=5)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame, text="Готов к работе",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM,
        )
        self.progress_label.grid(row=0, column=1, padx=10)

        # Логи
        self.log_text = ctk.CTkTextbox(
            bottom, height=140,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0A0A0C",
            text_color="#00FF88",
            border_color="#333333",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 12))

        self.log_text.bind("<Button-3>", self._show_log_context_menu)

    def _show_log_context_menu(self, event):
        """Контекстное меню для логов"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Копировать", command=lambda: self._copy_log_selection())
        menu.add_command(label="Очистить", command=lambda: self.log_text.delete("1.0", "end"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_log_selection(self):
        """Копирование выделенного в логах"""
        try:
            text = self.log_text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(text)
        except tk.TclError:
            pass

    def _process_log_queue(self):
        """Обработка очереди логов"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)

    # === Обработчики событий ===

    def _browse_video(self):
        """Выбор видеофайла"""
        path = filedialog.askopenfilename(
            title="Выберите видео",
            filetypes=[("Видео", "*.mp4 *.mov *.avi *.mkv *.webm"), ("Все файлы", "*.*")]
        )
        if path:
            self.video_path = Path(path)
            self.video_entry.delete(0, "end")
            self.video_entry.insert(0, str(self.video_path))
            self.video_preview.load_video(str(self.video_path))
            self.btn_quick_start.configure(state="normal")
            self.btn_refresh_preview.configure(state="normal")
            self.btn_fullscreen_preview.configure(state="normal")
            self.generate_btn.configure(state="normal" if self.highlights else "disabled")
            logging.info(f"Загружено видео: {self.video_path.name}")

    def _browse_music(self):
        """Выбор музыки"""
        path = filedialog.askopenfilename(
            title="Выберите музыку",
            filetypes=[("Аудио", "*.mp3 *.wav *.ogg *.m4a *.aac"), ("Все файлы", "*.*")]
        )
        if path:
            self.music_path = Path(path)
            self.music_entry.delete(0, "end")
            self.music_entry.insert(0, str(self.music_path))
            logging.info(f"Загружена музыка: {self.music_path.name}")

    def _add_banner(self):
        """Добавление рекламного баннера"""
        path = filedialog.askopenfilename(
            title="Выберите баннер (картинка или видео)",
            filetypes=[
                ("Медиа", "*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.mov *.avi *.webm"),
                ("Все файлы", "*.*")
            ]
        )
        if not path:
            return

        dialog = BannerDialog(self, path)
        self.wait_window(dialog)
        if dialog.result:
            banner = dialog.result
            self.ad_banners.append(banner)
            self._refresh_banners_list()
            logging.info(f"Добавлен баннер: {banner.path} @{banner.start_time}s × {banner.duration}s [{banner.position}]")

    def _refresh_banners_list(self):
        """Обновление списка баннеров в UI"""
        for w in self.banner_widgets:
            w.destroy()
        self.banner_widgets.clear()

        for i, banner in enumerate(self.ad_banners):
            frame = ctk.CTkFrame(self.banners_frame, fg_color="#2A2A2E", corner_radius=6)
            frame.grid(row=i, column=0, sticky="ew", pady=2)
            frame.grid_columnconfigure(1, weight=1)

            is_video = banner.path.lower().endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv'))
            icon = "🎬" if is_video else "🖼"
            name = Path(banner.path).name

            ctk.CTkLabel(frame, text=f"{icon} {name}", font=ctk.CTkFont(size=11)).grid(
                row=0, column=0, padx=8, pady=4, sticky="w"
            )
            ctk.CTkLabel(
                frame, text=f"@{banner.start_time:.1f}s × {banner.duration:.1f}s [{banner.position}]",
                font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_DIM,
            ).grid(row=0, column=1, padx=8, pady=4, sticky="e")
            ctk.CTkButton(frame, text="✕", width=24, height=24, fg_color=COLOR_ERROR,
                          command=lambda idx=i: self._remove_banner(idx)).grid(
                row=0, column=2, padx=5, pady=2
            )
            self.banner_widgets.append(frame)

    def _remove_banner(self, index: int):
        """Удаление баннера"""
        if 0 <= index < len(self.ad_banners):
            removed = self.ad_banners.pop(index)
            self._refresh_banners_list()
            logging.info(f"Удалён баннер: {removed.path}")

    def _refresh_preview_frame(self):
        """Обновляет текущий кадр превью"""
        if self.video_preview.is_loaded:
            self.video_preview.stop_playback()
            self.video_preview._show_frame(self.video_preview.current_frame)

    def _toggle_fullscreen_preview(self):
        """Разворачивает превью на весь экран (заглушка)"""
        if not self.video_preview.is_loaded:
            return
        # Просто ставим фокус на превью и делаем окно больше
        self.geometry("1800x1000")
        self.video_preview.canvas.focus_set()

    def _start_detection(self):
        """Запуск детекции хайлайтов"""
        if not self.video_path:
            messagebox.showerror("Ошибка", "Сначала загрузите видео!")
            return

        if self.processing:
            return

        self.processing = True
        self.detect_btn.configure(state="disabled", text="⏳ Идет анализ...")
        self.btn_quick_start.configure(state="disabled", text="⏳ Анализ...")
        self.generate_btn.configure(state="disabled")
        self.progress_var.set(0)
        self.progress_label.configure(text="Анализ видео...")
        self.preview_placeholder.grid_remove()

        thread = threading.Thread(target=self._detection_worker, daemon=True)
        thread.start()

    def _detection_worker(self):
        """Рабочий поток детекции"""
        try:
            subtitles = []
            if self.subtitles_enabled.get():
                self._update_progress(0.1, "Генерация субтитров...")
                engine = self.sub_engine_var.get()
                lang = self.sub_lang_var.get()
                translate = self.translate_var.get()
                subtitles = generate_subtitles(
                    str(self.video_path),
                    engine=engine,
                    language=lang,
                    translate=translate
                )
                logging.info(f"Сгенерировано {len(subtitles)} сегментов субтитров")

            self._update_progress(0.4, "Поиск хайлайтов...")
            CONFIG.min_clip_duration = self.min_dur_var.get()
            CONFIG.max_clip_duration = self.max_dur_var.get()
            CONFIG.max_clips_per_video = self.max_clips_var.get()
            CONFIG.blur_background = self.blur_bg_var.get()
            CONFIG.smart_crop = self.smart_crop_var.get()
            CONFIG.music_volume = self.music_vol_var.get()

            highlights = detect_highlights(str(self.video_path), subtitles)
            self.highlights = highlights
            self.subtitle_segments = subtitles

            self.after(0, self._on_detection_complete)

        except Exception as e:
            logging.error(f"Ошибка детекции: {e}")
            self.after(0, lambda: self._on_detection_error(str(e)))

    def _on_detection_complete(self):
        """Завершение детекции"""
        self.processing = False
        self.detect_btn.configure(state="normal", text="🔍 Найти хайлайты")
        self.btn_quick_start.configure(state="normal", text="▶ Найти хайлайты")
        self.generate_btn.configure(state="normal")
        self.progress_var.set(1.0)
        self.progress_label.configure(text=f"Найдено {len(self.highlights)} хайлайтов")
        self._render_highlights_list()
        logging.info(f"Детекция завершена: {len(self.highlights)} хайлайтов")

    def _on_detection_error(self, error: str):
        """Ошибка детекции"""
        self.processing = False
        self.detect_btn.configure(state="normal", text="🔍 Найти хайлайты")
        self.btn_quick_start.configure(state="normal", text="▶ Найти хайлайты")
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка детекции", error)

    def _update_progress(self, value: float, text: str):
        """Обновление прогресса из рабочего потока"""
        self.after(0, lambda: (self.progress_var.set(value), self.progress_label.configure(text=text)))

    def _render_highlights_list(self):
        """Отрисовка списка хайлайтов с превью-кадрами"""
        for w in self.highlight_widgets:
            w.destroy()
        self.highlight_widgets.clear()

        if not self.highlights:
            self.preview_placeholder.grid(row=0, column=0, pady=60)
            return

        self.preview_placeholder.grid_remove()

        for i, h in enumerate(self.highlights):
            frame = ctk.CTkFrame(self.highlights_list, fg_color="#2A2A2E", corner_radius=8)
            frame.grid(row=i, column=0, sticky="ew", pady=5, padx=5)
            frame.grid_columnconfigure(2, weight=1)

            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(frame, text="", variable=var, width=28)
            cb.grid(row=0, column=0, padx=8, pady=8)
            h.selected = var

            # Инфо о хайлайте
            info_frame = ctk.CTkFrame(frame, fg_color="transparent")
            info_frame.grid(row=0, column=1, sticky="w", padx=8, pady=8)
            info_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                info_frame, text=f"#{i+1}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_ACCENT,
            ).grid(row=0, column=0, sticky="w")

            time_text = f"{h.start:.1f}s – {h.end:.1f}s  ({h.duration:.1f}s)"
            ctk.CTkLabel(
                info_frame, text=time_text,
                font=ctk.CTkFont(family="Consolas", size=11),
                text_color=COLOR_TEXT,
            ).grid(row=1, column=0, sticky="w")

            ctk.CTkLabel(
                info_frame, text=f"Score: {h.score:.2f}",
                font=ctk.CTkFont(size=10),
                text_color=COLOR_SUCCESS,
            ).grid(row=2, column=0, sticky="w")

            reasons_text = ", ".join(h.reasons[:3])
            ctk.CTkLabel(
                frame, text=reasons_text,
                font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_DIM,
            ).grid(row=0, column=2, padx=8, pady=8, sticky="e")

            # Кнопка показа кадра в превью
            btn_preview = ctk.CTkButton(
                frame, text="▶ Кадр", width=55, height=28,
                command=lambda idx=i, start=h.start: self._preview_highlight(idx, start),
                fg_color="transparent",
                hover_color="#333339",
                border_width=1,
                border_color="#444444",
            )
            btn_preview.grid(row=0, column=3, padx=8, pady=8)

            self.highlight_widgets.append(frame)

    def _preview_highlight(self, index: int, start_time: float):
        """Показывает кадр хайлайта в видео-превью"""
        if not self.video_preview.is_loaded:
            return
        self.video_preview.stop_playback()
        frame_index = int(start_time * self.video_preview.fps)
        frame_index = max(0, min(frame_index, self.video_preview.total_frames - 1))
        self.video_preview._show_frame(frame_index)
        logging.info(f"Превью хайлайта #{index+1}: кадр на {start_time:.1f}s")

    def _start_generation(self):
        """Запуск генерации клипов"""
        if not self.video_path:
            messagebox.showerror("Ошибка", "Нет видео!")
            return

        selected = [h for h in self.highlights if getattr(h, 'selected', ctk.BooleanVar(value=True)).get()]
        if not selected:
            messagebox.showerror("Ошибка", "Выберите хотя бы один хайлайт!")
            return

        if self.processing:
            return

        self.processing = True
        self.generate_btn.configure(state="disabled", text="⏳ Рендер...")
        self.detect_btn.configure(state="disabled")
        self.btn_quick_start.configure(state="disabled", text="⏳ Рендер...")
        self.progress_var.set(0)

        thread = threading.Thread(target=self._generation_worker, args=(selected,), daemon=True)
        thread.start()

    def _generation_worker(self, highlights: List[HighlightSegment]):
        """Рабочий поток генерации"""
        try:
            def progress_cb(progress: float, text: str):
                self._update_progress(progress, text)

            output_dir = CONFIG.output_dir / self.platform_var.get()
            output_dir.mkdir(parents=True, exist_ok=True)

            ad_banners = []
            for b in self.ad_banners:
                ad_banners.append(AdBanner(
                    path=b.path,
                    start_time=b.start_time,
                    duration=b.duration,
                    position=b.position,
                    opacity=b.opacity
                ))

            results = create_clips(
                video_path=str(self.video_path),
                highlights=highlights,
                platform=self.platform_var.get(),
                music_path=str(self.music_path) if self.music_path else None,
                subtitle_segments=self.subtitle_segments if self.subtitles_enabled.get() else None,
                ad_banners=ad_banners if ad_banners else None,
                output_dir=output_dir,
                progress_callback=progress_cb
            )

            self.after(0, lambda: self._on_generation_complete(results))

        except Exception as e:
            logging.error(f"Ошибка генерации: {e}")
            self.after(0, lambda: self._on_generation_error(str(e)))

    def _on_generation_complete(self, results: List[Path]):
        """Завершение генерации"""
        self.processing = False
        self.generate_btn.configure(state="normal", text="🎬 Создать клипы")
        self.detect_btn.configure(state="normal")
        self.btn_quick_start.configure(state="normal", text="▶ Найти хайлайты")
        self.progress_var.set(1.0)
        self.progress_label.configure(text=f"Готово! Создано {len(results)} клипов")

        msg = f"Успешно создано {len(results)} клипов в папке:\n{CONFIG.output_dir / self.platform_var.get()}"
        messagebox.showinfo("Готово!", msg)

        import subprocess
        subprocess.Popen(f'explorer "{CONFIG.output_dir / self.platform_var.get()}"')

    def _on_generation_error(self, error: str):
        """Ошибка генерации"""
        self.processing = False
        self.generate_btn.configure(state="normal", text="🎬 Создать клипы")
        self.detect_btn.configure(state="normal")
        self.btn_quick_start.configure(state="normal", text="▶ Найти хайлайты")
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка генерации", error)


class BannerDialog(ctk.CTkToplevel):
    """Диалог добавления баннера"""

    def __init__(self, parent, banner_path: str):
        super().__init__(parent)
        self.title("Добавить рекламный баннер")
        self.geometry("500x470")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.banner_path = banner_path
        self.result: Optional[AdBanner] = None

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - self.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        # Путь к файлу
        ctk.CTkLabel(self, text="Файл:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=20, pady=15, sticky="w"
        )
        ctk.CTkLabel(self, text=Path(self.banner_path).name, text_color=COLOR_TEXT_DIM).grid(
            row=0, column=1, padx=20, pady=15, sticky="w"
        )

        # Время начала
        ctk.CTkLabel(self, text="Время начала (сек):").grid(
            row=1, column=0, padx=20, pady=10, sticky="w"
        )
        self.start_var = ctk.DoubleVar(value=0)
        ctk.CTkEntry(self, textvariable=self.start_var).grid(
            row=1, column=1, padx=20, pady=10, sticky="ew"
        )

        # Длительность
        ctk.CTkLabel(self, text="Длительность (сек):").grid(
            row=2, column=0, padx=20, pady=10, sticky="w"
        )
        self.dur_var = ctk.DoubleVar(value=5)
        ctk.CTkEntry(self, textvariable=self.dur_var).grid(
            row=2, column=1, padx=20, pady=10, sticky="ew"
        )

        # Позиция
        ctk.CTkLabel(self, text="Позиция:").grid(
            row=3, column=0, padx=20, pady=10, sticky="w"
        )
        self.pos_var = ctk.StringVar(value="overlay")
        pos_frame = ctk.CTkFrame(self, fg_color="transparent")
        pos_frame.grid(row=3, column=1, padx=20, pady=10, sticky="ew")
        for pos in ["overlay", "top", "bottom", "center"]:
            ctk.CTkRadioButton(pos_frame, text=pos.capitalize(),
                               variable=self.pos_var, value=pos).pack(side="left", padx=10)

        # Прозрачность
        ctk.CTkLabel(self, text="Прозрачность:").grid(
            row=4, column=0, padx=20, pady=10, sticky="w"
        )
        self.opacity_var = ctk.DoubleVar(value=1.0)
        opacity_frame = ctk.CTkFrame(self, fg_color="transparent")
        opacity_frame.grid(row=4, column=1, padx=20, pady=10, sticky="ew")
        opacity_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(opacity_frame, from_=0, to=1, variable=self.opacity_var).grid(
            row=0, column=0, sticky="ew", padx=5
        )
        self.opacity_label = ctk.CTkLabel(opacity_frame, text="100%")
        self.opacity_label.grid(row=0, column=1, padx=5)
        self.opacity_var.trace_add("write", lambda *_: self.opacity_label.configure(
            text=f"{int(self.opacity_var.get()*100)}%"
        ))

        # Кнопки
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, columnspan=2, pady=25)
        ctk.CTkButton(btn_frame, text="Отмена", command=self.destroy, fg_color="gray").pack(
            side="left", padx=10
        )
        ctk.CTkButton(btn_frame, text="Добавить", command=self._on_ok, fg_color=COLOR_ACCENT).pack(
            side="left", padx=10
        )

    def _on_ok(self):
        """Подтверждение"""
        self.result = AdBanner(
            path=self.banner_path,
            start_time=self.start_var.get(),
            duration=self.dur_var.get(),
            position=self.pos_var.get(),
            opacity=self.opacity_var.get()
        )
        self.destroy()


def main():
    """Точка входа"""
    app = ReelCutterApp()
    app.mainloop()


if __name__ == "__main__":
    main()