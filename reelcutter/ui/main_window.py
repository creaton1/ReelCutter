"""Главное окно ReelCutter — современный монтажный интерфейс (studio edit)."""
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

# ── Тема / палитра ─────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG      = "#0A0E17"   # главный фон (глубокий slate)
PANEL   = "#111827"   # панели / сайдбар
CARD    = "#161E2E"   # карточки
CARD_H  = "#1F2A44"   # карточка при наведении / выбрана
BORDER  = "#253042"   # границы
TEXT    = "#F3F4F6"
DIM     = "#94A3B8"
DIM2    = "#64748B"
ACCENT  = "#8B5CF6"   # фиолетовый акцент
ACCENT_H= "#7C3AED"
ACCENT_D= "#6D28D9"
CYAN    = "#06B6D4"
SUCCESS = "#10B981"
WARN    = "#F59E0B"
ERROR   = "#EF4444"
INK     = "#0B0C0F"

logger = logging.getLogger(__name__)

FONT_UI   = ("Segoe UI", 11)
FONT_UI_S = ("Segoe UI", 10)
FONT_UI_XS= ("Segoe UI", 9)
FONT_H1   = ("Segoe UI", 20, "bold")
FONT_H2   = ("Segoe UI", 13, "bold")
FONT_MONO = ("Consolas", 11)


class LogHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


# ── Виджет видео-превью ────────────────────────────────────
class VideoPreview(ctk.CTkFrame):
    """Плеер: показ кадров + play/pause + таймлайн"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=CARD, corner_radius=14, border_width=1,
                         border_color=BORDER, **kwargs)
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

        # Видео-полотно
        self.canvas = tk.Canvas(self, bg="#05070A", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))

        # Пустое состояние
        self.empty_label = ctk.CTkLabel(
            self.canvas, text="Видео не загружено",
            font=FONT_UI, text_color=DIM2,
        )
        self.canvas.create_window(0, 0, window=self.empty_label, anchor=tk.CENTER)
        self.canvas.bind("<Configure>", lambda e: self._center_empty())

        # Управление снизу
        self.controls = ctk.CTkFrame(self, fg_color="transparent", height=62)
        self.controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.controls.grid_propagate(False)
        self.controls.grid_columnconfigure(1, weight=1)

        self.btn_play = ctk.CTkButton(
            self.controls, text="▶", width=46, height=40, command=self._toggle_play,
            state="disabled", fg_color=ACCENT, hover_color=ACCENT_H, corner_radius=10,
            font=ctk.CTkFont(size=15),
        )
        self.btn_play.grid(row=0, column=0, padx=(0, 12))

        self.time_label = ctk.CTkLabel(
            self.controls, text="00:00 / 00:00", font=FONT_MONO,
            text_color=DIM, width=105,
        )
        self.time_label.grid(row=0, column=1, sticky="w")

        self.timeline = ctk.CTkSlider(
            self.controls, from_=0, to=100, command=self._on_seek, width=340,
            button_color=ACCENT, progress_color=ACCENT,
        )
        self.timeline.grid(row=0, column=2, sticky="ew", padx=10)

        self.video_label = ctk.CTkLabel(
            self.controls, text="", font=FONT_UI_XS, text_color=DIM2, width=140,
        )
        self.video_label.grid(row=0, column=3, sticky="e")

    def _center_empty(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.canvas.coords("all", cw // 2, ch // 2)

    def load_video(self, video_path):
        self.unload_video()
        self.video_path = Path(video_path)
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            self.video_label.configure(text="Ошибка загрузки", text_color=ERROR)
            return
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.is_loaded = True
        self.current_frame = 0
        self.current_time = 0.0
        self.empty_label.place_forget()
        self.video_label.configure(text=self.video_path.name[:32], text_color=DIM)
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
        self.btn_play.configure(state="disabled", text="▶", fg_color=ACCENT)
        self.timeline.configure(to=100)
        self.time_label.configure(text="00:00 / 00:00")
        self.canvas.delete("all")
        self.empty_label = ctk.CTkLabel(
            self.canvas, text="Видео не загружено",
            font=FONT_UI, text_color=DIM2,
        )
        self.canvas.create_window(0, 0, window=self.empty_label, anchor=tk.CENTER)
        self.canvas.bind("<Configure>", lambda e: self._center_empty())

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
        return f"{int(sec // 60):02d}:{int(sec % 60):02d}"

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
        self.btn_play.configure(text="⏸", fg_color=WARN, hover_color="#B45309")
        self._stop_event.clear()
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()

    def stop_playback(self):
        self.is_playing = False
        self.btn_play.configure(text="▶", fg_color=ACCENT, hover_color=ACCENT_H)
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


# ── Карточка хайлайта ──────────────────────────────────────
class HighlightCard(ctk.CTkFrame):
    """Одна строка хайлайта с чекбоксом, временем, счётом и кнопкой превью."""

    def __init__(self, parent, index: int, h: HighlightSegment, on_select, on_preview, **kwargs):
        super().__init__(parent, fg_color=CARD, corner_radius=10, border_width=1,
                         border_color=BORDER, **kwargs)
        self.index = index
        self.h = h
        self.on_select = on_select
        self.on_preview = on_preview
        self.selected_var = ctk.BooleanVar(value=True)
        h.selected = self.selected_var
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(2, weight=1)
        self.configure(height=64)
        self.grid_propagate(False)

        # Чекбокс выбора
        cb = ctk.CTkCheckBox(
            self, text="", variable=self.selected_var, width=26, height=26,
            fg_color=ACCENT, hover_color=ACCENT_H, command=self.on_select,
        )
        cb.grid(row=0, column=0, padx=12, pady=6)

        # Номер и время
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=4)

        num_lbl = ctk.CTkLabel(
            info, text=f"#{self.index + 1}", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT, anchor="w",
        )
        num_lbl.pack(anchor="w")
        time_lbl = ctk.CTkLabel(
            info, text=f"{self.h.start:.1f}s – {self.h.end:.1f}s  ({self.h.duration:.1f}s)",
            font=ctk.CTkFont(family="Consolas", size=11), text_color=TEXT, anchor="w",
        )
        time_lbl.pack(anchor="w")

        # Оценка (справа)
        score = ctk.CTkFrame(self, fg_color=CARD_H, corner_radius=8)
        score.grid(row=0, column=3, padx=10, pady=6)
        score.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            score, text=f"Score {self.h.score:.2f}", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=SUCCESS, anchor="e",
        ).grid(row=0, column=0, padx=8, pady=3)

        # Кнопка превью
        btn_prev = ctk.CTkButton(
            self, text="▶", width=34, height=30,
            command=lambda: self.on_preview(self.h.start),
            fg_color="transparent", hover_color=CARD_H,
            border_width=1, border_color=BORDER, font=ctk.CTkFont(size=13),
        )
        btn_prev.grid(row=0, column=4, padx=10, pady=6)

    def set_selected(self, value: bool):
        self.selected_var.set(value)

    def set_active(self, active: bool):
        self.configure(fg_color=CARD_H if active else CARD,
                       border_color=ACCENT if active else BORDER)


# ── Главное окно ───────────────────────────────────────────
class ReelCutterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ReelCutter — Studio")
        self.geometry("1600x980")
        self.minsize(1300, 860)
        self.configure(fg_color=BG)

        self.video_path: Optional[Path] = None
        self.music_path: Optional[Path] = None
        self.subtitle_segments: List[SubtitleSegment] = []
        self.highlights: List[HighlightSegment] = []
        self.ad_banners: List[AdBanner] = []
        self.processing = False
        self.log_queue = queue.Queue()
        self.highlight_cards: List[HighlightCard] = []

        self._setup_logging()
        self._build_ui()
        self._process_log_queue()
        self._toast_id = None

    # ── Логирование ────────────────────────────────────────
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

    # ── Сборка интерфейса ──────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=260)   # сайдбар
        self.grid_columnconfigure(1, weight=1)                # центр
        self.grid_columnconfigure(2, weight=0, minsize=340)   # правая панель
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=150)      # логи

        self._build_sidebar()
        self._build_center()
        self._build_right_panel()
        self._build_logs()

    # ── Логотип + навигация (левый сайдбар) ────────────────
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(3, weight=1)

        # Логотип
        logo_box = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_box.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 12))
        ctk.CTkLabel(
            logo_box, text="REELCUTTER", font=ctk.CTkFont(size=19, weight="bold"),
            text_color=TEXT, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            logo_box, text="viral clip studio", font=ctk.CTkFont(size=10),
            text_color=DIM2, anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        divider = ctk.CTkFrame(sidebar, fg_color=BORDER, height=1)
        divider.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 18))

        # Группа «Медиа»
        self._section_title(sidebar, "МЕДИА", row=2)
        media = ctk.CTkFrame(sidebar, fg_color="transparent")
        media.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        media.grid_columnconfigure(0, weight=1)
        media.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(media, text="Видео", font=FONT_UI_XS, text_color=DIM2,
                     anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.video_entry = ctk.CTkEntry(
            media, placeholder_text="файл видео…", height=36,
            font=FONT_UI, border_color=BORDER,
        )
        self.video_entry.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.btn_video = ctk.CTkButton(
            media, text="Открыть видео", height=40, command=self._browse_video,
            fg_color=ACCENT, hover_color=ACCENT_H, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.btn_video.grid(row=2, column=0, sticky="ew", pady=(0, 16))

        ctk.CTkLabel(media, text="Музыка", font=FONT_UI_XS, text_color=DIM2,
                     anchor="w").grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.music_entry = ctk.CTkEntry(
            media, placeholder_text="файл музыки…", height=36,
            font=FONT_UI, border_color=BORDER,
        )
        self.music_entry.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.btn_music = ctk.CTkButton(
            media, text="Открыть музыку", height=40, command=self._browse_music,
            fg_color=CARD, hover_color=CARD_H, border_width=1, border_color=BORDER,
            corner_radius=10, font=ctk.CTkFont(size=12),
        )
        self.btn_music.grid(row=5, column=0, sticky="ew", pady=(0, 20))

        # Баннеры
        self._section_title(media, "БАННЕРЫ", row=6)
        self.banners_frame = ctk.CTkFrame(media, fg_color="transparent")
        self.banners_frame.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        self.btn_add_banner = ctk.CTkButton(
            media, text="+ Добавить баннер", height=40, command=self._add_banner,
            fg_color=CARD, hover_color=CARD_H, border_width=1, border_color=BORDER,
            corner_radius=10, font=ctk.CTkFont(size=12),
        )
        self.btn_add_banner.grid(row=8, column=0, sticky="ew", pady=(0, 4))
        self.btn_clear_banners = ctk.CTkButton(
            media, text="Очистить баннеры", height=32, command=self._clear_banners,
            fg_color="transparent", hover_color=CARD_H, border_width=1,
            border_color=BORDER, corner_radius=8, font=ctk.CTkFont(size=11),
            text_color=DIM,
        )
        self.btn_clear_banners.grid(row=9, column=0, sticky="ew", pady=(0, 20))
        self.banner_widgets = []

        # Действия
        self._section_title(media, "ДЕЙСТВИЯ", row=10)
        self.btn_detect = ctk.CTkButton(
            media, text="🔍 Найти хайлайты", height=44, command=self._start_detection,
            fg_color=ACCENT, hover_color=ACCENT_H, corner_radius=12,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_detect.grid(row=11, column=0, sticky="ew", pady=(0, 10))
        self.btn_generate = ctk.CTkButton(
            media, text="🎬 Создать клипы", height=44, command=self._start_generation,
            state="disabled", fg_color=SUCCESS, hover_color="#0E9A6E",
            corner_radius=12, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_generate.grid(row=12, column=0, sticky="ew", pady=(0, 0))

    def _section_title(self, parent, text, row):
        lbl = ctk.CTkLabel(
            parent, text=text.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=DIM2, anchor="w",
        )
        lbl.grid(row=row, column=0, sticky="w", pady=(0, 6))
        return lbl

    # ── Центр: превью + хайлайты ──────────────────────────
    def _build_center(self):
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=0)   # превью
        center.grid_rowconfigure(1, weight=1)   # хайлайты

        # Превью
        self.video_preview = VideoPreview(center)
        self.video_preview.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        # Хайлайты
        hl_frame = ctk.CTkFrame(center, fg_color=CARD, corner_radius=14,
                                border_width=1, border_color=BORDER)
        hl_frame.grid(row=1, column=0, sticky="nsew")
        hl_frame.grid_columnconfigure(0, weight=1)
        hl_frame.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(hl_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="ХАЙЛАЙТЫ", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.hl_count_label = ctk.CTkLabel(
            header, text="0 найдено", font=ctk.CTkFont(size=11),
            text_color=SUCCESS, anchor="e",
        )
        self.hl_count_label.grid(row=0, column=1, sticky="e")

        self.highlights_list = ctk.CTkScrollableFrame(
            hl_frame, fg_color="transparent", scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=CARD_H,
        )
        self.highlights_list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 6))
        self.highlights_list.grid_columnconfigure(0, weight=1)

        self.preview_placeholder = ctk.CTkLabel(
            self.highlights_list,
            text="Загрузите видео и нажмите «Найти хайлайты»",
            text_color=DIM, font=ctk.CTkFont(size=13),
        )
        self.preview_placeholder.pack(pady=80)
        self.highlight_widgets = []

        # Пустое состояние хайлайтов (overlay)
        self.hl_empty = ctk.CTkFrame(hl_frame, fg_color="transparent")
        self.hl_empty.grid(row=2, column=0, sticky="nsew")
        ctk.CTkLabel(
            self.hl_empty, text="Хайлайты появятся после анализа",
            text_color=DIM2, font=FONT_UI,
        ).pack(expand=True)

    # ── Правая панель: свойства ────────────────────────────
    def _build_right_panel(self):
        dock = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        dock.grid(row=0, column=2, sticky="nsew")
        dock.grid_propagate(False)
        dock.grid_columnconfigure(0, weight=1)
        dock.grid_rowconfigure(1, weight=1)

        self._section_title(dock, "СВОЙСТВА", row=0)

        scroll = ctk.CTkScrollableFrame(dock, fg_color="transparent",
                                        scrollbar_button_color=BORDER,
                                        scrollbar_button_hover_color=CARD_H)
        scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0
        row = self._prop_section(scroll, row, "Платформа", self._prop_platform)
        row = self._prop_section(scroll, row, "Длительность клипов", self._prop_duration)
        row = self._prop_section(scroll, row, "Количество клипов", self._prop_clips)
        row = self._prop_section(scroll, row, "Субтитры", self._prop_subtitles)
        row = self._prop_section(scroll, row, "Видео", self._prop_video)
        row = self._prop_section(scroll, row, "Аудио", self._prop_audio)

        # отступ снизу
        ctk.CTkFrame(scroll, fg_color="transparent", height=24).grid(row=row, column=0, sticky="ew")

    def _prop_section(self, parent, start_row, title, builder):
        ctk.CTkLabel(
            parent, text=title.upper(), font=ctk.CTkFont(size=10, weight="bold"),
            text_color=DIM2, anchor="w",
        ).grid(row=start_row, column=0, sticky="w", padx=16, pady=(14, 6))
        builder(parent, start_row + 1)
        return start_row + 2

    def _prop_platform(self, parent, row):
        self.platform_var = ctk.StringVar(value=CONFIG.default_platform)
        pf = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
        pf.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        for i, (key, cfg) in enumerate(PLATFORMS.items()):
            ctk.CTkRadioButton(
                pf, text=f"{cfg.name} ({cfg.max_duration}s)",
                variable=self.platform_var, value=key,
                fg_color=ACCENT, hover_color=ACCENT_H,
                font=FONT_UI, text_color=TEXT,
            ).grid(row=i, column=0, sticky="w", padx=12, pady=6)

    def _prop_duration(self, parent, row):
        self.min_dur_var = ctk.DoubleVar(value=CONFIG.min_clip_duration)
        self.max_dur_var = ctk.DoubleVar(value=CONFIG.max_clip_duration)

        dur = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
        dur.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        dur.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dur, text="Минимум", font=FONT_UI_XS, text_color=DIM,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        ctk.CTkSlider(
            dur, from_=1, to=30, variable=self.min_dur_var, number_of_steps=29,
            button_color=ACCENT, progress_color=ACCENT,
        ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 4))
        self.min_dur_label = ctk.CTkLabel(
            dur, text=f"{CONFIG.min_clip_duration:.0f}с", font=FONT_MONO,
            text_color=TEXT,
        )
        self.min_dur_label.grid(row=1, column=2, padx=12, pady=(0, 4))
        self.min_dur_var.trace_add(
            "write", lambda *_: self.min_dur_label.configure(text=f"{self.min_dur_var.get():.0f}с"))

        ctk.CTkLabel(dur, text="Максимум", font=FONT_UI_XS, text_color=DIM,
                     anchor="w").grid(row=2, column=0, sticky="w", padx=12, pady=(8, 4))
        ctk.CTkSlider(
            dur, from_=10, to=180, variable=self.max_dur_var, number_of_steps=170,
            button_color=ACCENT, progress_color=ACCENT,
        ).grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 10))
        self.max_dur_label = ctk.CTkLabel(
            dur, text=f"{CONFIG.max_clip_duration:.0f}с", font=FONT_MONO,
            text_color=TEXT,
        )
        self.max_dur_label.grid(row=3, column=2, padx=12, pady=(0, 10))
        self.max_dur_var.trace_add(
            "write", lambda *_: self.max_dur_label.configure(text=f"{self.max_dur_var.get():.0f}с"))

    def _prop_clips(self, parent, row):
        self.max_clips_var = ctk.IntVar(value=CONFIG.max_clips_per_video)
        clips = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
        clips.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        clips.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(
            clips, from_=1, to=20, variable=self.max_clips_var, number_of_steps=19,
            button_color=ACCENT, progress_color=ACCENT,
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        self.clips_label = ctk.CTkLabel(
            clips, text=f"{CONFIG.max_clips_per_video}", font=FONT_MONO,
            text_color=TEXT,
        )
        self.clips_label.grid(row=0, column=1, padx=12, pady=10)
        self.max_clips_var.trace_add("write", lambda *_: self.clips_label.configure(text=f"{self.max_clips_var.get()}"))

    def _prop_subtitles(self, parent, row):
        self.subtitles_enabled = ctk.BooleanVar(value=True)
        self.sub_engine_var = ctk.StringVar(value="whisper")
        self.sub_lang_var = ctk.StringVar(value="auto")
        self.translate_var = ctk.BooleanVar(value=False)

        sub = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
        sub.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        sub.grid_columnconfigure(1, weight=1)

        ctk.CTkCheckBox(
            sub, text="Включить субтитры", variable=self.subtitles_enabled,
            fg_color=ACCENT, hover_color=ACCENT_H, font=FONT_UI,
            text_color=TEXT,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))

        ctk.CTkLabel(sub, text="Движок", font=FONT_UI_XS, text_color=DIM,
                     anchor="w").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))
        ctk.CTkOptionMenu(
            sub, values=["whisper", "vosk"], variable=self.sub_engine_var, width=140,
            fg_color=PANEL, button_color=ACCENT, font=FONT_UI,
        ).grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 6))

        ctk.CTkLabel(sub, text="Язык", font=FONT_UI_XS, text_color=DIM,
                     anchor="w").grid(row=2, column=0, sticky="w", padx=12, pady=(0, 4))
        ctk.CTkOptionMenu(
            sub, values=["auto", "ru", "en"], variable=self.sub_lang_var, width=140,
            fg_color=PANEL, button_color=ACCENT, font=FONT_UI,
        ).grid(row=2, column=1, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkCheckBox(
            sub, text="Перевести на английский", variable=self.translate_var,
            fg_color=ACCENT, hover_color=ACCENT_H, font=FONT_UI_S,
            text_color=TEXT,
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10))

    def _prop_video(self, parent, row):
        self.blur_bg_var = ctk.BooleanVar(value=CONFIG.blur_background)
        self.smart_crop_var = ctk.BooleanVar(value=CONFIG.smart_crop)

        vid = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
        vid.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkCheckBox(
            vid, text="Размытый фон", variable=self.blur_bg_var,
            fg_color=ACCENT, hover_color=ACCENT_H, font=FONT_UI,
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkCheckBox(
            vid, text="Умный кроп", variable=self.smart_crop_var,
            fg_color=ACCENT, hover_color=ACCENT_H, font=FONT_UI,
            text_color=TEXT,
        ).grid(row=0, column=1, sticky="w", padx=12, pady=8)

    def _prop_audio(self, parent, row):
        self.music_vol_var = ctk.DoubleVar(value=CONFIG.music_volume)

        aud = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
        aud.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        aud.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(aud, text="Громкость музыки", font=FONT_UI_XS,
                     text_color=DIM, anchor="w").grid(row=0, column=0, sticky="w",
                                                      padx=12, pady=(10, 4))
        ctk.CTkSlider(
            aud, from_=0, to=1, variable=self.music_vol_var, number_of_steps=100,
            button_color=ACCENT, progress_color=ACCENT,
        ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 4))
        self.music_vol_label = ctk.CTkLabel(
            aud, text=f"{int(CONFIG.music_volume * 100)}%", font=FONT_MONO,
            text_color=TEXT,
        )
        self.music_vol_label.grid(row=1, column=2, padx=12, pady=(0, 10))
        self.music_vol_var.trace_add(
            "write", lambda *_: self.music_vol_label.configure(
                text=f"{int(self.music_vol_var.get() * 100)}%"))

    # ── Логи + прогресс (низ) ──────────────────────────────
    def _build_logs(self):
        logs = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        logs.grid(row=1, column=0, columnspan=3, sticky="ew")
        logs.grid_columnconfigure(0, weight=1)
        logs.grid_rowconfigure(1, weight=1)

        self.progress_frame = ctk.CTkFrame(logs, fg_color="transparent")
        self.progress_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame, variable=self.progress_var, height=12,
            progress_color=ACCENT, fg_color=CARD,
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(
            self.progress_frame, text="Готов к работе",
            font=ctk.CTkFont(size=10), text_color=DIM,
        )
        self.progress_label.grid(row=0, column=1)

        self.log_text = ctk.CTkTextbox(
            logs, height=116, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#080A0F", text_color="#9BE89B", border_color=BORDER,
            border_width=1,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
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

    def _toast(self, message, color=ACCENT, duration=2500):
        if self._toast_id is not None:
            self.after_cancel(self._toast_id)
            self._toast_id = None
        toast = ctk.CTkLabel(
            self, text=message, font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT, fg_color=color, corner_radius=8,
        )
        toast.place(relx=0.5, rely=0.06, anchor="n")
        toast.lift()
        self._toast_id = self.after(duration, lambda: toast.destroy())

    # ── Обработчики файлов ─────────────────────────────────
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
            self._toast(f"Видео загружено: {self.video_path.name}")

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
            self._toast(f"Музыка загружена: {self.music_path.name}")

    def _clear_banners(self):
        self.ad_banners.clear()
        self._refresh_banners()
        logging.info("Баннеры очищены")
        self._toast("Баннеры очищены", color=WARN)

    def _add_banner(self):
        path = filedialog.askopenfilename(
            title="Выберите баннер",
            filetypes=[("Медиа", "*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.mov *.avi *.webm"),
                       ("Все файлы", "*.*")]
        )
        if not path:
            return
        dialog = BannerDialog(self, path)
        self.wait_window(dialog)
        if dialog.result:
            self.ad_banners.append(dialog.result)
            self._refresh_banners()
            logging.info(f"Добавлен баннер: {dialog.result.path}")
            self._toast("Баннер добавлен")

    def _refresh_banners(self):
        for w in self.banner_widgets:
            w.destroy()
        self.banner_widgets.clear()
        for i, banner in enumerate(self.ad_banners):
            frame = ctk.CTkFrame(self.banners_frame, fg_color=CARD, corner_radius=8)
            frame.pack(fill="x", pady=3)
            is_video = banner.path.lower().endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv'))
            icon = "🎬" if is_video else "🖼"
            ctk.CTkLabel(
                frame, text=f"{icon} {Path(banner.path).name}", font=ctk.CTkFont(size=10),
                text_color=TEXT, anchor="w",
            ).pack(side="left", padx=8, pady=4, fill="x", expand=True)
            ctk.CTkButton(
                frame, text="✕", width=24, height=24, fg_color=ERROR,
                hover_color="#DC2626", corner_radius=6,
                command=lambda idx=i: self._remove_banner(idx),
            ).pack(side="right", padx=4, pady=2)
            self.banner_widgets.append(frame)

    def _remove_banner(self, index):
        if 0 <= index < len(self.ad_banners):
            self.ad_banners.pop(index)
            self._refresh_banners()

    # ── Детекция ───────────────────────────────────────────
    def _start_detection(self):
        if not self.video_path:
            messagebox.showerror("Ошибка", "Сначала загрузите видео!")
            return
        if self.processing:
            return
        self.processing = True
        self.progress_var.set(0)
        self.progress_label.configure(text="Анализ видео…")
        self.preview_placeholder.pack(pady=80)
        threading.Thread(target=self._detection_worker, daemon=True).start()

    def _detection_worker(self):
        try:
            subtitles = []
            if self.subtitles_enabled.get():
                self._update_progress(0.1, "Генерация субтитров…")
                subtitles = generate_subtitles(
                    str(self.video_path), engine=self.sub_engine_var.get(),
                    language=self.sub_lang_var.get(), translate=self.translate_var.get(),
                )
                logging.info(f"Субтитры: {len(subtitles)} сегментов")

            self._update_progress(0.4, "Поиск хайлайтов…")
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
        self._toast(f"Найдено {len(self.highlights)} хайлайтов", color=SUCCESS)

    def _render_highlights(self):
        for w in self.highlight_widgets:
            w.destroy()
        self.highlight_widgets.clear()
        self.highlight_cards.clear()
        self.hl_count_label.configure(text=f"{len(self.highlights)} найдено")

        if not self.highlights:
            self.preview_placeholder.pack(pady=80)
            return

        self.preview_placeholder.pack_forget()
        self.hl_empty.grid_remove()

        for i, h in enumerate(self.highlights):
            card = HighlightCard(
                self.highlights_list, i, h,
                on_select=self._on_highlight_select,
                on_preview=self._preview_highlight,
            )
            card.pack(fill="x", pady=5, padx=2)
            self.highlight_widgets.append(card)
            self.highlight_cards.append(card)

    def _on_highlight_select(self):
        pass

    def _preview_highlight(self, start_time):
        if not self.video_preview.is_loaded:
            return
        self.video_preview.stop_playback()
        idx = int(start_time * self.video_preview.fps)
        idx = max(0, min(idx, self.video_preview.total_frames - 1))
        self.video_preview._show_frame(idx)

    # ── Генерация ──────────────────────────────────────────
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
        self.progress_label.configure(text="Рендер…")
        threading.Thread(target=self._generation_worker, args=(selected,), daemon=True).start()

    def _generation_worker(self, highlights):
        try:
            def cb(p, t):
                self._update_progress(p, t)
            output_dir = CONFIG.output_dir / self.platform_var.get()
            output_dir.mkdir(parents=True, exist_ok=True)
            banners = [AdBanner(b.path, b.start_time, b.duration, b.position, b.opacity)
                       for b in self.ad_banners]
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
        self._toast(f"Создано {len(results)} клипов", color=SUCCESS)

    def _on_error(self, error):
        self.processing = False
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка", error)
        self._toast(error, color=ERROR)

    def _update_progress(self, value, text):
        self.after(0, lambda: (self.progress_var.set(value), self.progress_label.configure(text=text)))


# ── Диалог баннера ─────────────────────────────────────────
class BannerDialog(ctk.CTkToplevel):
    def __init__(self, parent, banner_path):
        super().__init__(parent)
        self.title("Добавить баннер")
        self.geometry("500x470")
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
        pad = 20

        ctk.CTkLabel(self, text="Файл:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=pad, pady=16, sticky="w")
        ctk.CTkLabel(self, text=Path(self.banner_path).name, text_color=DIM).grid(
            row=0, column=1, padx=pad, pady=16, sticky="w")

        ctk.CTkLabel(self, text="Время начала (сек):").grid(
            row=1, column=0, padx=pad, pady=10, sticky="w")
        self.start_var = ctk.DoubleVar(value=0)
        ctk.CTkEntry(self, textvariable=self.start_var, border_color=BORDER).grid(
            row=1, column=1, padx=pad, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Длительность (сек):").grid(
            row=2, column=0, padx=pad, pady=10, sticky="w")
        self.dur_var = ctk.DoubleVar(value=5)
        ctk.CTkEntry(self, textvariable=self.dur_var, border_color=BORDER).grid(
            row=2, column=1, padx=pad, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Позиция:").grid(
            row=3, column=0, padx=pad, pady=10, sticky="w")
        self.pos_var = ctk.StringVar(value="overlay")
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.grid(row=3, column=1, padx=pad, pady=10, sticky="ew")
        for pos in ["overlay", "top", "bottom", "center"]:
            ctk.CTkRadioButton(
                pf, text=pos.capitalize(), variable=self.pos_var, value=pos,
                fg_color=ACCENT, hover_color=ACCENT_H,
            ).pack(side="left", padx=10)

        ctk.CTkLabel(self, text="Прозрачность:").grid(
            row=4, column=0, padx=pad, pady=10, sticky="w")
        self.opacity_var = ctk.DoubleVar(value=1.0)
        of = ctk.CTkFrame(self, fg_color="transparent")
        of.grid(row=4, column=1, padx=pad, pady=10, sticky="ew")
        of.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(
            of, from_=0, to=1, variable=self.opacity_var, button_color=ACCENT,
            progress_color=ACCENT,
        ).grid(row=0, column=0, sticky="ew", padx=5)
        self.opacity_label = ctk.CTkLabel(of, text="100%")
        self.opacity_label.grid(row=0, column=1, padx=5)
        self.opacity_var.trace_add("write", lambda *_: self.opacity_label.configure(
            text=f"{int(self.opacity_var.get() * 100)}%"))

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=5, column=0, columnspan=2, pady=24)
        ctk.CTkButton(
            bf, text="Отмена", command=self.destroy, fg_color=CARD,
            hover_color=CARD_H, border_width=1, border_color=BORDER,
            corner_radius=8, width=100,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            bf, text="Добавить", command=self._on_ok, fg_color=ACCENT,
            hover_color=ACCENT_H, corner_radius=8, width=100,
        ).pack(side="left", padx=10)

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
