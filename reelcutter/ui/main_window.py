"""Главное окно приложения ReelCutter на CustomTkinter"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import threading
import logging
import queue
import time
from typing import Optional, List, Callable

from ..core.config import CONFIG, PLATFORMS
from ..core.highlight_detector import HighlightSegment, detect_highlights
from ..core.subtitle_generator import SubtitleGenerator, SubtitleSegment, generate_subtitles
from ..core.video_composer import VideoComposer, AdBanner, create_clips

# Настройка темы
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """Хендлер для вывода логов в UI"""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class ReelCutterApp(ctk.CTk):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        self.title("ReelCutter - Авто-клипы для Reels/Shorts/TikTok")
        self.geometry("1200x800")
        self.minsize(1000, 700)

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

        # Очищаем существующие хендлеры
        for h in logger.handlers[:]:
            logger.removeHandler(h)

        # Консоль
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console)

        # UI очередь
        ui_handler = LogHandler(self.log_queue)
        ui_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        logger.addHandler(ui_handler)

    def _build_ui(self):
        """Построение интерфейса"""
        # Главный контейнер
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Верхняя панель - загрузка видео
        self._build_top_panel()

        # Центральная область - настройки и превью
        self._build_center_area()

        # Нижняя панель - логи и прогресс
        self._build_bottom_panel()

    def _build_top_panel(self):
        """Верхняя панель: видео, музыка, баннеры"""
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top.grid_columnconfigure(1, weight=1)

        # Видео
        ctk.CTkLabel(top, text="🎬 Видео:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        self.video_entry = ctk.CTkEntry(top, placeholder_text="Перетащите видеофайл или нажмите Обзор...")
        self.video_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(top, text="Обзор", width=80, command=self._browse_video).grid(
            row=0, column=2, padx=10, pady=10
        )

        # Музыка
        ctk.CTkLabel(top, text="🎵 Музыка:", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=0, padx=10, pady=5, sticky="w"
        )
        self.music_entry = ctk.CTkEntry(top, placeholder_text="Файл музыки (опционально)")
        self.music_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(top, text="Обзор", width=80, command=self._browse_music).grid(
            row=1, column=2, padx=10, pady=5
        )

        # Рекламные баннеры
        ctk.CTkLabel(top, text="📢 Баннеры:", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, padx=10, pady=5, sticky="w"
        )
        self.banners_frame = ctk.CTkFrame(top, fg_color="transparent")
        self.banners_frame.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        self.banners_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(top, text="+ Добавить", width=80, command=self._add_banner).grid(
            row=2, column=2, padx=10, pady=5
        )

        # Список баннеров (динамический)
        self.banner_widgets = []

    def _build_center_area(self):
        """Центральная область: настройки слева, превью справа"""
        center = ctk.CTkFrame(self)
        center.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        center.grid_columnconfigure(0, weight=1)
        center.grid_columnconfigure(1, weight=1)
        center.grid_rowconfigure(0, weight=1)

        # Левая панель - настройки
        self._build_settings_panel(center)

        # Правая панель - превью хайлайтов
        self._build_preview_panel(center)

    def _build_settings_panel(self, parent):
        """Панель настроек"""
        settings = ctk.CTkScrollableFrame(parent, width=400)
        settings.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        settings.grid_columnconfigure(0, weight=1)

        # Платформа
        ctk.CTkLabel(settings, text="📱 Платформа", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, pady=10, sticky="w"
        )
        self.platform_var = ctk.StringVar(value=CONFIG.default_platform)
        platform_frame = ctk.CTkFrame(settings, fg_color="transparent")
        platform_frame.grid(row=1, column=0, sticky="ew", pady=5)
        for i, (key, cfg) in enumerate(PLATFORMS.items()):
            rb = ctk.CTkRadioButton(
                platform_frame, text=f"{cfg.name} ({cfg.max_duration}s)",
                variable=self.platform_var, value=key
            )
            rb.grid(row=0, column=i, padx=5, sticky="w")

        # Длительность клипов
        ctk.CTkLabel(settings, text="⏱ Длительность клипов", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=2, column=0, pady=(20, 10), sticky="w"
        )

        dur_frame = ctk.CTkFrame(settings, fg_color="transparent")
        dur_frame.grid(row=3, column=0, sticky="ew", pady=5)
        dur_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dur_frame, text="Мин:").grid(row=0, column=0, padx=5)
        self.min_dur_var = ctk.DoubleVar(value=CONFIG.min_clip_duration)
        ctk.CTkSlider(dur_frame, from_=1, to=30, variable=self.min_dur_var, number_of_steps=29).grid(
            row=0, column=1, sticky="ew", padx=5
        )
        self.min_dur_label = ctk.CTkLabel(dur_frame, text=f"{CONFIG.min_clip_duration:.0f}с")
        self.min_dur_label.grid(row=0, column=2, padx=5)
        self.min_dur_var.trace_add("write", lambda *_: self.min_dur_label.configure(text=f"{self.min_dur_var.get():.0f}с"))

        ctk.CTkLabel(dur_frame, text="Макс:").grid(row=1, column=0, padx=5)
        self.max_dur_var = ctk.DoubleVar(value=CONFIG.max_clip_duration)
        ctk.CTkSlider(dur_frame, from_=10, to=180, variable=self.max_dur_var, number_of_steps=170).grid(
            row=1, column=1, sticky="ew", padx=5
        )
        self.max_dur_label = ctk.CTkLabel(dur_frame, text=f"{CONFIG.max_clip_duration:.0f}с")
        self.max_dur_label.grid(row=1, column=2, padx=5)
        self.max_dur_var.trace_add("write", lambda *_: self.max_dur_label.configure(text=f"{self.max_dur_var.get():.0f}с"))

        # Количество клипов
        ctk.CTkLabel(settings, text="🔢 Кол-во клипов", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=4, column=0, pady=(20, 10), sticky="w"
        )
        self.max_clips_var = ctk.IntVar(value=CONFIG.max_clips_per_video)
        clips_frame = ctk.CTkFrame(settings, fg_color="transparent")
        clips_frame.grid(row=5, column=0, sticky="ew", pady=5)
        clips_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkSlider(clips_frame, from_=1, to=20, variable=self.max_clips_var, number_of_steps=19).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=5
        )
        self.clips_label = ctk.CTkLabel(clips_frame, text=f"{CONFIG.max_clips_per_video}")
        self.clips_label.grid(row=0, column=2, padx=5)
        self.max_clips_var.trace_add("write", lambda *_: self.clips_label.configure(text=f"{self.max_clips_var.get()}"))

        # Субтитры
        ctk.CTkLabel(settings, text="💬 Субтитры", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=6, column=0, pady=(20, 10), sticky="w"
        )

        sub_frame = ctk.CTkFrame(settings, fg_color="transparent")
        sub_frame.grid(row=7, column=0, sticky="ew", pady=5)
        sub_frame.grid_columnconfigure(1, weight=1)

        self.subtitles_enabled = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sub_frame, text="Включить субтитры", variable=self.subtitles_enabled).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=5
        )

        ctk.CTkLabel(sub_frame, text="Движок:").grid(row=1, column=0, padx=5, sticky="w")
        self.sub_engine_var = ctk.StringVar(value="whisper")
        ctk.CTkOptionMenu(sub_frame, values=["whisper", "vosk"], variable=self.sub_engine_var).grid(
            row=1, column=1, sticky="ew", padx=5
        )

        ctk.CTkLabel(sub_frame, text="Язык:").grid(row=2, column=0, padx=5, sticky="w")
        self.sub_lang_var = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(sub_frame, values=["auto", "ru", "en"], variable=self.sub_lang_var).grid(
            row=2, column=1, sticky="ew", padx=5
        )

        self.translate_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sub_frame, text="Перевести на английский", variable=self.translate_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=5
        )

        # Видео настройки
        ctk.CTkLabel(settings, text="🎨 Видео", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=8, column=0, pady=(20, 10), sticky="w"
        )

        vid_frame = ctk.CTkFrame(settings, fg_color="transparent")
        vid_frame.grid(row=9, column=0, sticky="ew", pady=5)

        self.blur_bg_var = ctk.BooleanVar(value=CONFIG.blur_background)
        ctk.CTkCheckBox(vid_frame, text="Размытый фон (blur background)", variable=self.blur_bg_var).grid(
            row=0, column=0, sticky="w", pady=2
        )

        self.smart_crop_var = ctk.BooleanVar(value=CONFIG.smart_crop)
        ctk.CTkCheckBox(vid_frame, text="Умный кроп (по лицам)", variable=self.smart_crop_var).grid(
            row=1, column=0, sticky="w", pady=2
        )

        # Аудио настройки
        ctk.CTkLabel(settings, text="🔊 Аудио", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=10, column=0, pady=(20, 10), sticky="w"
        )

        aud_frame = ctk.CTkFrame(settings, fg_color="transparent")
        aud_frame.grid(row=11, column=0, sticky="ew", pady=5)
        aud_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(aud_frame, text="Громкость музыки:").grid(row=0, column=0, padx=5, sticky="w")
        self.music_vol_var = ctk.DoubleVar(value=CONFIG.music_volume)
        ctk.CTkSlider(aud_frame, from_=0, to=1, variable=self.music_vol_var, number_of_steps=100).grid(
            row=0, column=1, sticky="ew", padx=5
        )
        self.music_vol_label = ctk.CTkLabel(aud_frame, text=f"{int(CONFIG.music_volume*100)}%")
        self.music_vol_label.grid(row=0, column=2, padx=5)
        self.music_vol_var.trace_add("write", lambda *_: self.music_vol_label.configure(text=f"{int(self.music_vol_var.get()*100)}%"))

    def _build_preview_panel(self, parent):
        """Панель превью хайлайтов"""
        preview = ctk.CTkFrame(parent)
        preview.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)

        # Заголовок с кнопками
        header = ctk.CTkFrame(preview, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="🎯 Найденные хайлайты", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        self.detect_btn = ctk.CTkButton(btn_frame, text="🔍 Найти хайлайты", command=self._start_detection)
        self.detect_btn.grid(row=0, column=0, padx=5)

        self.generate_btn = ctk.CTkButton(btn_frame, text="🎬 Создать клипы", command=self._start_generation, state="disabled")
        self.generate_btn.grid(row=0, column=1, padx=5)

        # Список хайлайтов
        self.highlights_list = ctk.CTkScrollableFrame(preview)
        self.highlights_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.highlights_list.grid_columnconfigure(0, weight=1)

        # Плейсхолдер
        self.preview_placeholder = ctk.CTkLabel(
            self.highlights_list,
            text="Загрузите видео и нажмите \"Найти хайлайты\"",
            text_color="gray"
        )
        self.preview_placeholder.grid(row=0, column=0, pady=50)

        self.highlight_widgets = []

    def _build_bottom_panel(self):
        """Нижняя панель: прогресс и логи"""
        bottom = ctk.CTkFrame(self, height=200)
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, weight=1)
        bottom.grid_propagate(False)

        # Прогресс бар
        self.progress_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        self.progress_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, variable=self.progress_var)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=5)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Готов к работе")
        self.progress_label.grid(row=0, column=1, padx=10)

        # Логи
        self.log_text = ctk.CTkTextbox(bottom, height=150, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Контекстное меню для логов
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
            self.generate_btn.configure(state="normal" if self.video_path else "disabled")
            logging.info(f"Loaded video: {self.video_path.name}")

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
            logging.info(f"Loaded music: {self.music_path.name}")

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

        # Диалог настроек баннера
        dialog = BannerDialog(self, path)
        self.wait_window(dialog)
        if dialog.result:
            banner = dialog.result
            self.ad_banners.append(banner)
            self._refresh_banners_list()
            logging.info(f"Added banner: {banner.path} at {banner.start_time}s for {banner.duration}s")

    def _refresh_banners_list(self):
        """Обновление списка баннеров в UI"""
        for w in self.banner_widgets:
            w.destroy()
        self.banner_widgets.clear()

        for i, banner in enumerate(self.ad_banners):
            frame = ctk.CTkFrame(self.banners_frame)
            frame.grid(row=i, column=0, sticky="ew", pady=2)
            frame.grid_columnconfigure(1, weight=1)

            # Тип иконки
            is_video = banner.path.lower().endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv'))
            icon = "🎬" if is_video else "🖼"
            name = Path(banner.path).name

            ctk.CTkLabel(frame, text=f"{icon} {name}").grid(row=0, column=0, padx=10, pady=5)
            ctk.CTkLabel(frame, text=f"@{banner.start_time:.1f}s × {banner.duration:.1f}s [{banner.position}]").grid(
                row=0, column=1, padx=10, pady=5
            )
            ctk.CTkButton(frame, text="✕", width=30, fg_color="red",
                          command=lambda idx=i: self._remove_banner(idx)).grid(
                row=0, column=2, padx=5, pady=2
            )
            self.banner_widgets.append(frame)

    def _remove_banner(self, index: int):
        """Удаление баннера"""
        if 0 <= index < len(self.ad_banners):
            removed = self.ad_banners.pop(index)
            self._refresh_banners_list()
            logging.info(f"Removed banner: {removed.path}")

    def _start_detection(self):
        """Запуск детекции хайлайтов в отдельном потоке"""
        if not self.video_path:
            messagebox.showerror("Ошибка", "Сначала загрузите видео!")
            return

        if self.processing:
            return

        self.processing = True
        self.detect_btn.configure(state="disabled", text="⏳ Идет анализ...")
        self.generate_btn.configure(state="disabled")
        self.progress_var.set(0)
        self.progress_label.configure(text="Анализ видео...")
        self.preview_placeholder.grid_remove()

        thread = threading.Thread(target=self._detection_worker, daemon=True)
        thread.start()

    def _detection_worker(self):
        """Рабочий поток детекции"""
        try:
            # 1. Генерация субтитров (еśli включено)
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
                logging.info(f"Generated {len(subtitles)} subtitle segments")

            # 2. Детекция хайлайтов
            self._update_progress(0.4, "Поиск хайлайтов...")
            # Обновляем конфиг из UI
            CONFIG.min_clip_duration = self.min_dur_var.get()
            CONFIG.max_clip_duration = self.max_dur_var.get()
            CONFIG.max_clips_per_video = self.max_clips_var.get()
            CONFIG.blur_background = self.blur_bg_var.get()
            CONFIG.smart_crop = self.smart_crop_var.get()
            CONFIG.music_volume = self.music_vol_var.get()

            highlights = detect_highlights(str(self.video_path), subtitles)
            self.highlights = highlights
            self.subtitle_segments = subtitles

            # 3. Обновление UI в главном потоке
            self.after(0, self._on_detection_complete)

        except Exception as e:
            logging.error(f"Detection failed: {e}")
            self.after(0, lambda: self._on_detection_error(str(e)))

    def _on_detection_complete(self):
        """Завершение детекции"""
        self.processing = False
        self.detect_btn.configure(state="normal", text="🔍 Найти хайлайты")
        self.generate_btn.configure(state="normal")
        self.progress_var.set(1.0)
        self.progress_label.configure(text=f"Найдено {len(self.highlights)} хайлайтов")
        self._render_highlights_list()

    def _on_detection_error(self, error: str):
        """Ошибка детекции"""
        self.processing = False
        self.detect_btn.configure(state="normal", text="🔍 Найти хайлайты")
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка детекции", error)

    def _update_progress(self, value: float, text: str):
        """Обновление прогресса из рабочего потока"""
        self.after(0, lambda: (self.progress_var.set(value), self.progress_label.configure(text=text)))

    def _render_highlights_list(self):
        """Отрисовка списка хайлайтов"""
        for w in self.highlight_widgets:
            w.destroy()
        self.highlight_widgets.clear()

        if not self.highlights:
            self.preview_placeholder.grid(row=0, column=0, pady=50)
            return

        self.preview_placeholder.grid_remove()

        for i, h in enumerate(self.highlights):
            frame = ctk.CTkFrame(self.highlights_list)
            frame.grid(row=i, column=0, sticky="ew", pady=3, padx=5)
            frame.grid_columnconfigure(1, weight=1)

            # Чекбокс для выбора
            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(frame, text="", variable=var, width=30)
            cb.grid(row=0, column=0, padx=5, pady=5)
            h.selected = var  # сохраняем ссылку

            # Инфо
            info_text = f"#{i+1}  {h.start:.1f}s – {h.end:.1f}s  ({h.duration:.1f}s)  Score: {h.score:.2f}"
            ctk.CTkLabel(frame, text=info_text, font=ctk.CTkFont(family="Consolas", size=11)).grid(
                row=0, column=1, sticky="w", padx=10
            )

            # Причины
            reasons_text = ", ".join(h.reasons[:3])
            ctk.CTkLabel(frame, text=reasons_text, text_color="gray", font=ctk.CTkFont(size=10)).grid(
                row=0, column=2, padx=10, sticky="e"
            )

            self.highlight_widgets.append(frame)

    def _start_generation(self):
        """Запуск генерации клипов"""
        if not self.video_path:
            messagebox.showerror("Ошибка", "Нет видео!")
            return

        # Фильтруем выбранные хайлайты
        selected = [h for h in self.highlights if getattr(h, 'selected', ctk.BooleanVar(value=True)).get()]
        if not selected:
            messagebox.showerror("Ошибка", "Выберите хотя бы один хайлайт!")
            return

        if self.processing:
            return

        self.processing = True
        self.generate_btn.configure(state="disabled", text="⏳ Рендер...")
        self.detect_btn.configure(state="disabled")
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

            # Конвертируем баннеры
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
            logging.error(f"Generation failed: {e}")
            self.after(0, lambda: self._on_generation_error(str(e)))

    def _on_generation_complete(self, results: List[Path]):
        """Завершение генерации"""
        self.processing = False
        self.generate_btn.configure(state="normal", text="🎬 Создать клипы")
        self.detect_btn.configure(state="normal")
        self.progress_var.set(1.0)
        self.progress_label.configure(text=f"Готово! Создано {len(results)} клипов")

        # Показываем результат
        msg = f"Успешно создано {len(results)} клипов в папке:\n{CONFIG.output_dir / self.platform_var.get()}"
        messagebox.showinfo("Готово!", msg)

        # Открываем папку
        import subprocess
        subprocess.Popen(f'explorer "{CONFIG.output_dir / self.platform_var.get()}"')

    def _on_generation_error(self, error: str):
        """Ошибка генерации"""
        self.processing = False
        self.generate_btn.configure(state="normal", text="🎬 Создать клипы")
        self.detect_btn.configure(state="normal")
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка генерации", error)


class BannerDialog(ctk.CTkToplevel):
    """Диалог добавления баннера"""

    def __init__(self, parent, banner_path: str):
        super().__init__(parent)
        self.title("Добавить рекламный баннер")
        self.geometry("450x400")
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
        ctk.CTkLabel(self, text=Path(self.banner_path).name, text_color="gray").grid(
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
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ctk.CTkButton(btn_frame, text="Отмена", command=self.destroy, fg_color="gray").pack(
            side="left", padx=10
        )
        ctk.CTkButton(btn_frame, text="Добавить", command=self._on_ok).pack(
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