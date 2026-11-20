"""Главное окно ReelCutter — панельный (studio) интерфейс"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import threading
import logging
import queue
import time
from typing import Optional, List

import cv2
from PIL import Image, ImageTk

from ..core.config import CONFIG, PLATFORMS
from ..core.highlight_detector import HighlightSegment, detect_highlights
from ..core.subtitle_generator import SubtitleSegment, generate_subtitles
from ..core.video_composer import AdBanner, create_clips

# ── Тема ────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Палитра studio-стиля
BG      = "#0B0C0F"   # фон окна
PANEL   = "#15161A"   # панели
PANEL2  = "#1D1F24"   # вложенные панели / карточки
BORDER  = "#2A2D33"   # границы
TEXT    = "#E6E8EC"
DIM     = "#8B9098"
ACCENT  = "#3B82F6"   # синий акцент
SUCCESS = "#22C55E"
WARN    = "#F59E0B"
ERROR   = "#EF4444"

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


# ── Виджет видео-превью ─────────────────────────────────
class VideoPreview(ctk.CTkFrame):
    """Плеер: показ кадров + play/pause + таймлайн"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=PANEL2, corner_radius=8, **kwargs)
        self.video_path: Optional[Path] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.fps = 30
        self.total_frames = 0
        self.duration = 0.0
        self.current_frame = 0
        self.current_time = 0.0
        self.is_playing = False
        self.is_loaded = False
        self._stop_event = threading.Event()
        self._play_thread: Optional[threading.Thread] = None

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg="#000000", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.controls = ctk.CTkFrame(self, fg_color="transparent", height=56)
        self.controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.controls.grid_propagate(False)
        self.controls.grid_columnconfigure(1, weight=1)

        self.btn_play = ctk.CTkButton(
            self.controls, text="▶", width=44, height=38, command=self._toggle_play,
            state="disabled", fg_color=ACCENT, hover_color="#2E6FD8", corner_radius=6,
        )
        self.btn_play.grid(row=0, column=0, padx=(0, 10))

        self.time_label = ctk.CTkLabel(
            self.controls, text="00:00 / 00:00", font=ctk.CTkFont(size=12, family="Consolas"),
            text_color=DIM, width=90,
        )
        self.time_label.grid(row=0, column=1, sticky="w")

        self.timeline = ctk.CTkSlider(
            self.controls, from_=0, to=100, command=self._on_seek, width=300,
            button_color=ACCENT, progress_color=ACCENT,
        )
        self.timeline.grid(row=0, column=2, sticky="ew", padx=8)

        self.video_label = ctk.CTkLabel(
            self.controls, text="", font=ctk.CTkFont(size=11), text_color=DIM, width=150,
        )
        self.video_label.grid(row=0, column=3, sticky="e")

    def load_video(self, video_path):
        self.unload_video()
        self.video_path = Path(video_path)
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            self.video_label.configure(text="Ошибка", text_color=ERROR)
            return
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.is_loaded = True
        self.current_frame = 0
        self.current_time = 0.0
        self.video_label.configure(text=self.video_path.name[:30], text_color=DIM)
        self.btn_play.configure(state="normal")
        self.timeline.configure(to=max(self.duration, 1))
        self._show_frame(0)
        logger.info(f"Превью загружено: {self.video_path.name} ({self.duration:.1f}s)")

    def unload_video(self):
        self.stop_playback()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.video_path = None
        self.is_loaded = False
        self.current_frame = 0
        self.current_time = 0.0
        self.duration = 0.0
        self.video_label.configure(text="")
        self.btn_play.configure(state="disabled", text="▶")
        self.timeline.configure(to=100)
        self.time_label.configure(text="00:00 / 00:00")
        self.canvas.delete("all")

    def _show_frame(self, frame_index):
        if not self.is_loaded or not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        if not ret:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        cw = self.canvas.winfo_width() or 600
        ch = self.canvas.winfo_height() or 340
        scale = min(cw / img.width, ch / img.height)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo
        self.current_frame = frame_index
        self.current_time = frame_index / self.fps if self.fps > 0 else 0
        self.timeline.set(self.current_time)
        self.time_label.configure(text=f"{self._fmt(self.current_time)} / {self._fmt(self.duration)}")

    @staticmethod
    def _fmt(sec):
        return f"{int(sec//60):02d}:{int(sec%60):02d}"

    def _toggle_play(self):
        if not self.is_loaded:
            return
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if not self.is_loaded or self.is_playing:
            return
        self.is_playing = True
        self.btn_play.configure(text="⏸", fg_color=WARN)
        self._stop_event.clear()
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()

    def stop_playback(self):
        self.is_playing = False
        self.btn_play.configure(text="▶", fg_color=ACCENT)
        self._stop_event.set()

    def _play_loop(self):
        while self.is_playing and not self._stop_event.is_set():
            if self.current_frame >= self.total_frames - 1:
                self.stop_playback()
                break
            self.after(0, self._show_frame, self.current_frame + 1)
            time.sleep(1 / self.fps)

    def _on_seek(self, value):
        if not self.is_loaded:
            return
        self.stop_playback()
        idx = int(float(value) * self.fps)
        idx = max(0, min(idx, self.total_frames - 1))
        self._show_frame(idx)

    def destroy(self):
        self.stop_playback()
        if self.cap:
            self.cap.release()
        super().destroy()


# ── Главное окно ────────────────────────────────────────
class ReelCutterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ReelCutter — Studio")
        self.geometry("1500x920")
        self.minsize(1280, 820)
        self.configure(fg_color=BG)

        self.video_path: Optional[Path] = None
        self.music_path: Optional[Path] = None
        self.subtitle_segments: List[SubtitleSegment] = []
        self.highlights: List[HighlightSegment] = []
        self.ad_banners: List[AdBanner] = []
        self.processing = False
        self.log_queue = queue.Queue()

        self._setup_logging()
        self._build_ui()
        self._process_log_queue()

    def _setup_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        for h in logger.handlers[:]:
            logger.removeHandler(h)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console)
        ui = LogHandler(self.log_queue)
        ui.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        logger.addHandler(ui)

    # ── Layout ──────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=230)  # левый док
        self.grid_columnconfigure(1, weight=1)                # центр
        self.grid_columnconfigure(2, weight=0, minsize=330)   # правый док
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=160)      # логи

        self._build_left_dock()
        self._build_center()
        self._build_right_dock()
        self._build_logs()

    def _section_title(self, parent, text):
        lbl = ctk.CTkLabel(
            parent, text=text.upper(),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=DIM, anchor="w",
        )
        lbl.pack(fill="x", padx=14, pady=(14, 6))
        return lbl

    def _build_left_dock(self):
        """Левая колонка: медиа-файлы"""
        dock = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, width=230)
        dock.grid(row=0, column=0, sticky="nsew")
        dock.grid_propagate(False)

        # Логотип
        logo = ctk.CTkLabel(
            dock, text="⛏ ReelCutter",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT, anchor="w",
        )
        logo.pack(fill="x", padx=14, pady=(16, 8))

        ctk.CTkLabel(
            dock, text="Studio",
            font=ctk.CTkFont(size=11), text_color=DIM, anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 8))

        # Видео
        self._section_title(dock, "Видео")
        self.video_entry = ctk.CTkEntry(
            dock, placeholder_text="файл видео...",
            height=32, font=ctk.CTkFont(size=11), border_color=BORDER,
        )
        self.video_entry.pack(fill="x", padx=14, pady=(0, 4))
        self.btn_video = ctk.CTkButton(
            dock, text="Открыть видео", height=32, command=self._browse_video,
            fg_color=ACCENT, hover_color="#2E6FD8", corner_radius=6,
        )
        self.btn_video.pack(fill="x", padx=14, pady=(0, 8))

        # Музыка
        self._section_title(dock, "Музыка")
        self.music_entry = ctk.CTkEntry(
            dock, placeholder_text="файл музыки...",
            height=32, font=ctk.CTkFont(size=11), border_color=BORDER,
        )
        self.music_entry.pack(fill="x", padx=14, pady=(0, 4))
        self.btn_music = ctk.CTkButton(
            dock, text="Открыть музыку", height=32, command=self._browse_music,
            fg_color=PANEL2, hover_color="#2A2D33", border_width=1,
            border_color=BORDER, corner_radius=6,
        )
        self.btn_music.pack(fill="x", padx=14, pady=(0, 8))

        # Баннеры
        self._section_title(dock, "Баннеры")
        self.banners_frame = ctk.CTkFrame(dock, fg_color="transparent")
        self.banners_frame.pack(fill="x", padx=14, pady=(0, 4))
        self.btn_add_banner = ctk.CTkButton(
            dock, text="+ Добавить баннер", height=32, command=self._add_banner,
            fg_color=PANEL2, hover_color="#2A2D33", border_width=1,
            border_color=BORDER, corner_radius=6,
        )
        self.btn_add_banner.pack(fill="x", padx=14, pady=(0, 8))
        self.banner_widgets = []

        # Кнопки действий (внизу дока)
        ctk.CTkButton(
            dock, text="🔍 Найти хайлайты", height=40, command=self._start_detection,
            fg_color=ACCENT, hover_color="#2E6FD8", corner_radius=6,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(fill="x", padx=14, pady=(20, 8))
        self.btn_generate = ctk.CTkButton(
            dock, text="🎬 Создать клипы", height=40, command=self._start_generation,
            state="disabled", fg_color=SUCCESS, hover_color="#1DA84E",
            corner_radius=6, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_generate.pack(fill="x", padx=14, pady=(0, 16))

    def _build_center(self):
        """Центральная колонка: превью + хайлайты"""
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=1)

        # Превью сверху
        self.video_preview = VideoPreview(center)
        self.video_preview.grid(row=0, column=0, sticky="nsew")

        # Хайлайты снизу
        hl_frame = ctk.CTkFrame(center, fg_color=PANEL, corner_radius=8)
        hl_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        hl_frame.grid_columnconfigure(0, weight=1)
        hl_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(hl_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="ХАЙЛАЙТЫ",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=DIM,
        ).grid(row=0, column=0, sticky="w")
        self.hl_count_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=11), text_color=SUCCESS,
        )
        self.hl_count_label.grid(row=0, column=1, sticky="e")

        self.highlights_list = ctk.CTkScrollableFrame(hl_frame, fg_color="transparent")
        self.highlights_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.highlights_list.grid_columnconfigure(0, weight=1)

        self.preview_placeholder = ctk.CTkLabel(
            self.highlights_list, text="Загрузите видео и нажмите «Найти хайлайты»",
            text_color=DIM, font=ctk.CTkFont(size=13),
        )
        self.preview_placeholder.pack(pady=60)
        self.highlight_widgets = []

    def _build_right_dock(self):
        """Правая колонка: свойства / настройки"""
        dock = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, width=330)
        dock.grid(row=0, column=2, sticky="nsew")
        dock.grid_propagate(False)
        dock.grid_columnconfigure(0, weight=1)
        dock.grid_rowconfigure(1, weight=1)

        self._section_title(dock, "Свойства")

        scroll = ctk.CTkScrollableFrame(dock, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # ── Платформа ──
        ctk.CTkLabel(
            scroll, text="Платформа", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(8, 6))

        self.platform_var = ctk.StringVar(value=CONFIG.default_platform)
        pf = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
        pf.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        for i, (key, cfg) in enumerate(PLATFORMS.items()):
            ctk.CTkRadioButton(
                pf, text=f"{cfg.name} ({cfg.max_duration}s)",
                variable=self.platform_var, value=key,
                fg_color=ACCENT, hover_color=ACCENT,
            ).grid(row=i, column=0, sticky="w", padx=10, pady=5)

        # ── Длительность ──
        ctk.CTkLabel(
            scroll, text="Длительность клипов", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=14, pady=(8, 6))

        dur = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
        dur.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 12))
        dur.grid_columnconfigure(1, weight=1)

        self.min_dur_var = ctk.DoubleVar(value=CONFIG.min_clip_duration)
        ctk.CTkLabel(dur, text="Мин", text_color=DIM, font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=8, pady=4)
        ctk.CTkSlider(dur, from_=1, to=30, variable=self.min_dur_var, number_of_steps=29,
                      button_color=ACCENT, progress_color=ACCENT).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.min_dur_label = ctk.CTkLabel(dur, text=f"{CONFIG.min_clip_duration:.0f}с", width=34, text_color=TEXT, font=ctk.CTkFont(size=11))
        self.min_dur_label.grid(row=0, column=2, padx=8, pady=4)
        self.min_dur_var.trace_add("write", lambda *_: self.min_dur_label.configure(text=f"{self.min_dur_var.get():.0f}с"))

        self.max_dur_var = ctk.DoubleVar(value=CONFIG.max_clip_duration)
        ctk.CTkLabel(dur, text="Макс", text_color=DIM, font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=8, pady=4)
        ctk.CTkSlider(dur, from_=10, to=180, variable=self.max_dur_var, number_of_steps=170,
                      button_color=ACCENT, progress_color=ACCENT).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        self.max_dur_label = ctk.CTkLabel(dur, text=f"{CONFIG.max_clip_duration:.0f}с", width=34, text_color=TEXT, font=ctk.CTkFont(size=11))
        self.max_dur_label.grid(row=1, column=2, padx=8, pady=4)
        self.max_dur_var.trace_add("write", lambda *_: self.max_dur_label.configure(text=f"{self.max_dur_var.get():.0f}с"))

        # ── Количество клипов ──
        ctk.CTkLabel(
            scroll, text="Количество клипов", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=4, column=0, sticky="w", padx=14, pady=(8, 6))

        clips = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
        clips.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 12))
        clips.grid_columnconfigure(0, weight=1)

        self.max_clips_var = ctk.IntVar(value=CONFIG.max_clips_per_video)
        ctk.CTkSlider(clips, from_=1, to=20, variable=self.max_clips_var, number_of_steps=19,
                      button_color=ACCENT, progress_color=ACCENT).grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        self.clips_label = ctk.CTkLabel(clips, text=f"{CONFIG.max_clips_per_video}", width=30, text_color=TEXT, font=ctk.CTkFont(size=12))
        self.clips_label.grid(row=0, column=1, padx=8, pady=6)
        self.max_clips_var.trace_add("write", lambda *_: self.clips_label.configure(text=f"{self.max_clips_var.get()}"))

        # ── Субтитры ──
        ctk.CTkLabel(
            scroll, text="Субтитры", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=6, column=0, sticky="w", padx=14, pady=(8, 6))

        sub = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
        sub.grid(row=7, column=0, sticky="ew", padx=14, pady=(0, 12))
        sub.grid_columnconfigure(1, weight=1)

        self.subtitles_enabled = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sub, text="Включить субтитры", variable=self.subtitles_enabled,
                        fg_color=ACCENT, hover_color=ACCENT).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        ctk.CTkLabel(sub, text="Движок", text_color=DIM, font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.sub_engine_var = ctk.StringVar(value="whisper")
        ctk.CTkOptionMenu(sub, values=["whisper", "vosk"], variable=self.sub_engine_var, width=130,
                          fg_color=PANEL, button_color=ACCENT).grid(row=1, column=1, padx=10, pady=4, sticky="ew")

        ctk.CTkLabel(sub, text="Язык", text_color=DIM, font=ctk.CTkFont(size=11)).grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self.sub_lang_var = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(sub, values=["auto", "ru", "en"], variable=self.sub_lang_var, width=130,
                          fg_color=PANEL, button_color=ACCENT).grid(row=2, column=1, padx=10, pady=4, sticky="ew")

        self.translate_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sub, text="Перевести на английский", variable=self.translate_var,
                        fg_color=ACCENT, hover_color=ACCENT).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        # ── Видео ──
        ctk.CTkLabel(
            scroll, text="Видео", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=8, column=0, sticky="w", padx=14, pady=(8, 6))

        vid = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
        vid.grid(row=9, column=0, sticky="ew", padx=14, pady=(0, 12))

        self.blur_bg_var = ctk.BooleanVar(value=CONFIG.blur_background)
        ctk.CTkCheckBox(vid, text="Размытый фон", variable=self.blur_bg_var,
                        fg_color=ACCENT, hover_color=ACCENT).grid(row=0, column=0, sticky="w", padx=10, pady=4)
        self.smart_crop_var = ctk.BooleanVar(value=CONFIG.smart_crop)
        ctk.CTkCheckBox(vid, text="Умный кроп", variable=self.smart_crop_var,
                        fg_color=ACCENT, hover_color=ACCENT).grid(row=0, column=1, sticky="w", padx=10, pady=4)

        # ── Аудио ──
        ctk.CTkLabel(
            scroll, text="Аудио", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=10, column=0, sticky="w", padx=14, pady=(8, 6))

        aud = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
        aud.grid(row=11, column=0, sticky="ew", padx=14, pady=(0, 12))
        aud.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(aud, text="Громкость", text_color=DIM, font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=10, pady=4, sticky="w")
        self.music_vol_var = ctk.DoubleVar(value=CONFIG.music_volume)
        ctk.CTkSlider(aud, from_=0, to=1, variable=self.music_vol_var, number_of_steps=100,
                      button_color=ACCENT, progress_color=ACCENT).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.music_vol_label = ctk.CTkLabel(aud, text=f"{int(CONFIG.music_volume*100)}%", width=40, text_color=TEXT, font=ctk.CTkFont(size=11))
        self.music_vol_label.grid(row=0, column=2, padx=10, pady=4)
        self.music_vol_var.trace_add("write", lambda *_: self.music_vol_label.configure(text=f"{int(self.music_vol_var.get()*100)}%"))

    def _build_logs(self):
        """Нижняя панель логов"""
        logs = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        logs.grid(row=1, column=0, columnspan=3, sticky="ew")
        logs.grid_columnconfigure(0, weight=1)
        logs.grid_rowconfigure(1, weight=1)

        self.progress_frame = ctk.CTkFrame(logs, fg_color="transparent")
        self.progress_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, variable=self.progress_var, height=10,
                                               progress_color=ACCENT, fg_color=PANEL2)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Готов к работе", font=ctk.CTkFont(size=11), text_color=DIM)
        self.progress_label.grid(row=0, column=1)

        self.log_text = ctk.CTkTextbox(
            logs, height=110, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#07080A", text_color="#9BE89B", border_color=BORDER,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.log_text.bind("<Button-3>", self._log_context_menu)

    def _log_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Копировать", command=self._copy_log)
        menu.add_command(label="Очистить", command=lambda: self.log_text.delete("1.0", "end"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_log(self):
        try:
            text = self.log_text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(text)
        except tk.TclError:
            pass

    def _process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)

    # ── Обработчики ─────────────────────────────────────
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="Выберите видео",
            filetypes=[("Видео", "*.mp4 *.mov *.avi *.mkv *.webm"), ("Все файлы", "*.*")]
        )
        if path:
            self.video_path = Path(path)
            self.video_entry.delete(0, "end")
            self.video_entry.insert(0, str(self.video_path))
            self.video_preview.load_video(str(self.video_path))
            self.btn_generate.configure(state="normal" if self.highlights else "disabled")
            logging.info(f"Загружено видео: {self.video_path.name}")

    def _browse_music(self):
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
        path = filedialog.askopenfilename(
            title="Выберите баннер",
            filetypes=[("Медиа", "*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.mov *.avi *.webm"), ("Все файлы", "*.*")]
        )
        if not path:
            return
        dialog = BannerDialog(self, path)
        self.wait_window(dialog)
        if dialog.result:
            self.ad_banners.append(dialog.result)
            self._refresh_banners()
            logging.info(f"Добавлен баннер: {dialog.result.path}")

    def _refresh_banners(self):
        for w in self.banner_widgets:
            w.destroy()
        self.banner_widgets.clear()
        for i, banner in enumerate(self.ad_banners):
            frame = ctk.CTkFrame(self.banners_frame, fg_color=PANEL2, corner_radius=6)
            frame.pack(fill="x", pady=2)
            is_video = banner.path.lower().endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv'))
            icon = "🎬" if is_video else "🖼"
            ctk.CTkLabel(frame, text=f"{icon} {Path(banner.path).name}", font=ctk.CTkFont(size=10),
                         text_color=TEXT, anchor="w").pack(side="left", padx=8, pady=3, fill="x", expand=True)
            ctk.CTkButton(frame, text="✕", width=24, height=24, fg_color=ERROR,
                          command=lambda idx=i: self._remove_banner(idx)).pack(side="right", padx=4, pady=2)
            self.banner_widgets.append(frame)

    def _remove_banner(self, index):
        if 0 <= index < len(self.ad_banners):
            self.ad_banners.pop(index)
            self._refresh_banners()

    def _start_detection(self):
        if not self.video_path:
            messagebox.showerror("Ошибка", "Сначала загрузите видео!")
            return
        if self.processing:
            return
        self.processing = True
        self.progress_var.set(0)
        self.progress_label.configure(text="Анализ видео...")
        self.preview_placeholder.pack_forget()
        threading.Thread(target=self._detection_worker, daemon=True).start()

    def _detection_worker(self):
        try:
            subtitles = []
            if self.subtitles_enabled.get():
                self._update_progress(0.1, "Генерация субтитров...")
                subtitles = generate_subtitles(
                    str(self.video_path), engine=self.sub_engine_var.get(),
                    language=self.sub_lang_var.get(), translate=self.translate_var.get(),
                )
                logging.info(f"Субтитры: {len(subtitles)} сегментов")

            self._update_progress(0.4, "Поиск хайлайтов...")
            CONFIG.min_clip_duration = self.min_dur_var.get()
            CONFIG.max_clip_duration = self.max_dur_var.get()
            CONFIG.max_clips_per_video = self.max_clips_var.get()
            CONFIG.blur_background = self.blur_bg_var.get()
            CONFIG.smart_crop = self.smart_crop_var.get()
            CONFIG.music_volume = self.music_vol_var.get()

            self.highlights = detect_highlights(str(self.video_path), subtitles)
            self.subtitle_segments = subtitles
            self.after(0, self._on_detection_complete)
        except Exception as e:
            logging.error(f"Ошибка детекции: {e}")
            self.after(0, lambda: self._on_error(str(e)))

    def _on_detection_complete(self):
        self.processing = False
        self.progress_var.set(1.0)
        self.progress_label.configure(text=f"Найдено {len(self.highlights)} хайлайтов")
        self.btn_generate.configure(state="normal")
        self._render_highlights()
        logging.info(f"Детекция завершена: {len(self.highlights)} хайлайтов")

    def _render_highlights(self):
        for w in self.highlight_widgets:
            w.destroy()
        self.highlight_widgets.clear()
        self.hl_count_label.configure(text=f"{len(self.highlights)} найдено")

        if not self.highlights:
            self.preview_placeholder.pack(pady=60)
            return

        for i, h in enumerate(self.highlights):
            frame = ctk.CTkFrame(self.highlights_list, fg_color=PANEL2, corner_radius=6)
            frame.pack(fill="x", pady=3)
            frame.grid_columnconfigure(2, weight=1)

            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(frame, text="", variable=var, width=28, fg_color=ACCENT)
            cb.grid(row=0, column=0, padx=8, pady=6)
            h.selected = var

            info = ctk.CTkFrame(frame, fg_color="transparent")
            info.grid(row=0, column=1, sticky="w", padx=4, pady=4)

            ctk.CTkLabel(info, text=f"#{i+1}", font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=ACCENT, anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=f"{h.start:.1f}s – {h.end:.1f}s ({h.duration:.1f}s)",
                         font=ctk.CTkFont(family="Consolas", size=11), text_color=TEXT, anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=f"Score {h.score:.2f}", font=ctk.CTkFont(size=10),
                         text_color=SUCCESS, anchor="w").pack(anchor="w")

            ctk.CTkButton(frame, text="▶", width=36, height=28,
                          command=lambda s=h.start: self._preview_highlight(s),
                          fg_color="transparent", hover_color="#2A2D33",
                          border_width=1, border_color=BORDER).grid(row=0, column=3, padx=8, pady=6)

            self.highlight_widgets.append(frame)

    def _preview_highlight(self, start_time):
        if not self.video_preview.is_loaded:
            return
        self.video_preview.stop_playback()
        idx = int(start_time * self.video_preview.fps)
        idx = max(0, min(idx, self.video_preview.total_frames - 1))
        self.video_preview._show_frame(idx)

    def _start_generation(self):
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
        self.progress_var.set(0)
        self.progress_label.configure(text="Рендер...")
        threading.Thread(target=self._generation_worker, args=(selected,), daemon=True).start()

    def _generation_worker(self, highlights):
        try:
            def cb(p, t):
                self._update_progress(p, t)
            output_dir = CONFIG.output_dir / self.platform_var.get()
            output_dir.mkdir(parents=True, exist_ok=True)
            banners = [AdBanner(b.path, b.start_time, b.duration, b.position, b.opacity) for b in self.ad_banners]
            results = create_clips(
                video_path=str(self.video_path), highlights=highlights,
                platform=self.platform_var.get(),
                music_path=str(self.music_path) if self.music_path else None,
                subtitle_segments=self.subtitle_segments if self.subtitles_enabled.get() else None,
                ad_banners=banners or None,
                output_dir=output_dir, progress_callback=cb,
            )
            self.after(0, lambda: self._on_generation_complete(results))
        except Exception as e:
            logging.error(f"Ошибка генерации: {e}")
            self.after(0, lambda: self._on_error(str(e)))

    def _on_generation_complete(self, results):
        self.processing = False
        self.progress_var.set(1.0)
        self.progress_label.configure(text=f"Готово! Создано {len(results)} клипов")
        messagebox.showinfo("Готово!", f"Создано {len(results)} клипов в:\n{CONFIG.output_dir / self.platform_var.get()}")
        import subprocess
        subprocess.Popen(f'explorer "{CONFIG.output_dir / self.platform_var.get()}"')

    def _on_error(self, error):
        self.processing = False
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка", error)

    def _update_progress(self, value, text):
        self.after(0, lambda: (self.progress_var.set(value), self.progress_label.configure(text=text)))


# ── Диалог баннера ──────────────────────────────────────
class BannerDialog(ctk.CTkToplevel):
    def __init__(self, parent, banner_path):
        super().__init__(parent)
        self.title("Добавить баннер")
        self.geometry("460x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.banner_path = banner_path
        self.result: Optional[AdBanner] = None
        self._build_ui()
        self._center()

    def _center(self):
        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - self.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text="Файл:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=14, sticky="w")
        ctk.CTkLabel(self, text=Path(self.banner_path).name, text_color=DIM).grid(row=0, column=1, padx=20, pady=14, sticky="w")

        ctk.CTkLabel(self, text="Время начала (сек):").grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.start_var = ctk.DoubleVar(value=0)
        ctk.CTkEntry(self, textvariable=self.start_var, border_color=BORDER).grid(row=1, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Длительность (сек):").grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.dur_var = ctk.DoubleVar(value=5)
        ctk.CTkEntry(self, textvariable=self.dur_var, border_color=BORDER).grid(row=2, column=1, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Позиция:").grid(row=3, column=0, padx=20, pady=10, sticky="w")
        self.pos_var = ctk.StringVar(value="overlay")
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.grid(row=3, column=1, padx=20, pady=10, sticky="ew")
        for pos in ["overlay", "top", "bottom", "center"]:
            ctk.CTkRadioButton(pf, text=pos.capitalize(), variable=self.pos_var, value=pos,
                               fg_color=ACCENT, hover_color=ACCENT).pack(side="left", padx=8)

        ctk.CTkLabel(self, text="Прозрачность:").grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.opacity_var = ctk.DoubleVar(value=1.0)
        of = ctk.CTkFrame(self, fg_color="transparent")
        of.grid(row=4, column=1, padx=20, pady=10, sticky="ew")
        of.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(of, from_=0, to=1, variable=self.opacity_var, button_color=ACCENT,
                      progress_color=ACCENT).grid(row=0, column=0, sticky="ew", padx=5)
        self.opacity_label = ctk.CTkLabel(of, text="100%")
        self.opacity_label.grid(row=0, column=1, padx=5)
        self.opacity_var.trace_add("write", lambda *_: self.opacity_label.configure(text=f"{int(self.opacity_var.get()*100)}%"))

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=5, column=0, columnspan=2, pady=20)
        ctk.CTkButton(bf, text="Отмена", command=self.destroy, fg_color=PANEL2,
                      hover_color="#2A2D33", border_width=1, border_color=BORDER).pack(side="left", padx=10)
        ctk.CTkButton(bf, text="Добавить", command=self._on_ok, fg_color=ACCENT,
                      hover_color="#2E6FD8").pack(side="left", padx=10)

    def _on_ok(self):
        self.result = AdBanner(
            path=self.banner_path, start_time=self.start_var.get(),
            duration=self.dur_var.get(), position=self.pos_var.get(),
            opacity=self.opacity_var.get(),
        )
        self.destroy()


def main():
    app = ReelCutterApp()
    app.mainloop()


if __name__ == "__main__":
    main()