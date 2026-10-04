"""FFClass: a compact native PySide6 interface.

The media operations live in encoder.py. This module owns only widgets, navigation,
initial setup and the small JSON files that remember the user's choices.
"""
import json
import os
import platform
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
    QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget,
)

from encoder import MediaEngine


BASE = Path(__file__).resolve().parent

TEXT = {
    "RU": {
        "welcome": "Добро пожаловать в FFClass", "setup_hint": "Укажите имя, язык и оформление. Затем проверим компьютер.",
        "name": "Ваше имя", "language": "Язык", "theme": "Тема", "dark": "Тёмная", "light": "Светлая",
        "not_scanned": "Компьютер ещё не проверен", "continue": "Продолжить", "scanning": "Проверяем компьютер…",
        "home": "Главная", "files": "Медиафайлы", "pc": "ПК", "home_hint": "Выберите видео и задачу — остальное сделаем автоматически.",
        "video": "Видео для обработки", "no_file": "Файл не выбран", "choose": "Выбрать видео", "reading": "Считываем файл…",
        "task": "Что сделать с видео?", "task_hint": "Выберите задачу, затем укажите параметры.",
        "archive": "Сжать для хранения", "send25": "Уменьшить до 25 МБ", "send100": "Уменьшить до 100 МБ",
        "audio": "Извлечь звук", "remux": "Сменить контейнер без перекодирования",
        "format_video": "Формат видео", "format_audio": "Формат звука", "quality": "Качество и скорость",
        "fast": "Быстро", "balanced": "Баланс", "quality_high": "Высокое качество",
        "resolution": "Разрешение", "original": "Как в исходном видео", "advanced": "Дополнительные параметры",
        "fps": "Частота кадров", "codec": "Видеокодек", "auto": "Автоматически",
        "trim_start": "Начало, сек", "trim_end": "Конец, сек (0 — до конца)",
        "start": "Начать обработку", "starting": "Начинаем обработку…", "preparing": "Подготовка…",
        "cancel": "Отменить", "cancelled": "Обработка отменена", "done": "Готово: ", "remaining": "Осталось",
        "files_hint": "Результаты обработки за последнее время.", "open_folder": "Открыть папку результата",
        "os": "Система", "cpu": "Процессор", "gpu": "Графика", "ram_gb": "Память", "rec": "Кодировщик",
        "refresh": "Обновить сведения о ПК", "profile": "Профиль", "profile_name": "Имя", "save": "Сохранить",
        "select_dialog": "Выберите видео", "no_history": "Обработанных файлов пока нет", "error": "Ошибка обработки",
        "archive_hint": "Меньше размер, качество подбирается автоматически.",
        "send_hint": "Приложение рассчитает битрейт под выбранный лимит.",
        "audio_hint": "Получится отдельный звуковой файл.",
        "remux_hint": "Быстрая смена контейнера без изменения видео и звука; кодеки должны подходить формату.",
    },
    "EN": {
        "welcome": "Welcome to FFClass", "setup_hint": "Choose your name, language, and theme. Then we'll check this computer.",
        "name": "Your name", "language": "Language", "theme": "Theme", "dark": "Dark", "light": "Light",
        "not_scanned": "Computer not checked yet", "continue": "Continue", "scanning": "Checking computer…",
        "home": "Home", "files": "Media Files", "pc": "Computer", "home_hint": "Choose a video and a task. We'll handle the rest.",
        "video": "Video to process", "no_file": "No file selected", "choose": "Choose video", "reading": "Reading video…",
        "task": "What would you like to do?", "task_hint": "Choose a task, then adjust its options.",
        "archive": "Compress for storage", "send25": "Limit to 25 MB", "send100": "Limit to 100 MB",
        "audio": "Extract audio", "remux": "Change container without re-encoding",
        "format_video": "Video format", "format_audio": "Audio format", "quality": "Quality and speed",
        "fast": "Fast", "balanced": "Balanced", "quality_high": "High quality",
        "resolution": "Resolution", "original": "Keep original resolution", "advanced": "Additional options",
        "fps": "Frame rate", "codec": "Video codec", "auto": "Automatic",
        "trim_start": "Start, seconds", "trim_end": "End, seconds (0 = full duration)",
        "start": "Start processing", "starting": "Starting processing…", "preparing": "Preparing…",
        "cancel": "Cancel", "cancelled": "Processing cancelled", "done": "Done: ", "remaining": "Remaining",
        "files_hint": "Your recent processed files.", "open_folder": "Open output folder",
        "os": "System", "cpu": "Processor", "gpu": "Graphics", "ram_gb": "Memory", "rec": "Encoder",
        "refresh": "Refresh computer details", "profile": "Profile", "profile_name": "Name", "save": "Save",
        "select_dialog": "Choose a video", "no_history": "No processed files yet", "error": "Processing error",
        "archive_hint": "Smaller file size with automatically selected quality.",
        "send_hint": "FFClass calculates the bitrate for the selected size limit.",
        "audio_hint": "Creates a separate audio file.",
        "remux_hint": "Quick container change without re-encoding; streams must be compatible with the chosen format.",
    },
}

TEXT["RU"].update({
    "wizard": "Настройка обработки", "close_wizard": "← На главную", "next": "Продолжить →", "back": "← Назад",
    "step_indicator": "Шаг {step} из {total}", "compress_flow": "Сжать видео", "audio_flow": "Исправить или изменить звук",
    "remux_flow": "Быстро сменить контейнер", "compress_flow_hint": "Сжатие для отправки или хранения.",
    "audio_flow_hint": "Исправление дорожки для монтажа, замена или удаление звука.",
    "remux_flow_hint": "Перепаковка совместимых потоков без потери качества.",
    "compress_question": "Куда нужно отправить файл?", "audio_question": "Какая проблема со звуком?",
    "remux_question": "Что нужно перепаковать в MP4?", "question_hint": "Выберите один вариант, затем нажмите «Продолжить».",
    "discord": "Discord / Email · до 25 МБ", "telegram": "Telegram / мессенджеры", "disk": "Освободить место на диске",
    "davinci": "Нет звука в DaVinci Resolve (Linux)", "change_audio": "Изменить формат звука",
    "remove_audio": "Удалить звук из видео", "mkv_source": "MKV → MP4", "mov_source": "MOV → MP4",
    "webm_source": "WEBM → MP4", "audio_details": "Как подготовить аудио?",
    "compress_details": "Что важнее при обработке?", "remux_details": "Подготовка перепаковки",
    "audio_detail_hint": "Выберите формат звука и каналы.", "compress_detail_hint": "Скорость или качество, разрешение и при необходимости дополнительные параметры.",
    "remux_detail_hint": "Потоки будут скопированы, если MP4 их поддерживает.", "channels": "Каналы звука",
    "source_channels": "Оставить исходные", "stereo_channels": "Преобразовать 5.1 в стерео 2.0",
    "priority": "Приоритет", "speed": "Скорость · аппаратное ускорение при наличии",
    "max_quality": "Качество · кодирование на CPU", "summary_title": "Проверьте выбор",
    "summary_warning": "Итоговый размер и скорость зависят от файла. Несовместимые потоки нельзя перепаковать без перекодирования.",
    "remux_warning": "Для MP4 нужна совместимость кодеков. Для WEBM она не гарантируется; при ошибке потребуется перекодирование.",
    "wrong_source": "Выбран вариант {source}, но файл имеет расширение {actual}. Вернитесь на шаг назад и выберите исходный формат.",
    "pcm_hint": "Звук PCM в контейнере MOV; видео копируется, если исходный кодек совместим.",
    "remove_hint": "Звуковая дорожка будет удалена; дополнительные параметры не нужны.",
    "no_size_guarantee": "Размер до 25 МБ — цель с запасом, точный результат проверяется после обработки.",
})
TEXT["EN"].update({
    "wizard": "Processing setup", "close_wizard": "← Home", "next": "Continue →", "back": "← Back",
    "step_indicator": "Step {step} of {total}", "compress_flow": "Compress video", "audio_flow": "Fix or change audio",
    "remux_flow": "Quick container change", "compress_flow_hint": "Compress for sharing or storage.",
    "audio_flow_hint": "Fix the track for editing, convert or remove audio.",
    "remux_flow_hint": "Move compatible streams without losing quality.",
    "compress_question": "Where will you send the file?", "audio_question": "What is wrong with the sound?",
    "remux_question": "What do you want to remux to MP4?", "question_hint": "Choose one answer, then continue.",
    "discord": "Discord / Email · up to 25 MB", "telegram": "Telegram / messengers", "disk": "Save disk space",
    "davinci": "No sound in DaVinci Resolve (Linux)", "change_audio": "Change audio format",
    "remove_audio": "Remove sound from video", "mkv_source": "MKV → MP4", "mov_source": "MOV → MP4",
    "webm_source": "WEBM → MP4", "audio_details": "How should audio be prepared?",
    "compress_details": "What matters most?", "remux_details": "Remux setup",
    "audio_detail_hint": "Choose the audio format and channels.", "compress_detail_hint": "Choose speed or quality, resolution and optional details.",
    "remux_detail_hint": "Streams will be copied if MP4 supports them.", "channels": "Audio channels",
    "source_channels": "Keep original channels", "stereo_channels": "Convert 5.1 to stereo 2.0",
    "priority": "Priority", "speed": "Speed · hardware acceleration if available",
    "max_quality": "Quality · CPU encoding", "summary_title": "Review your choice",
    "summary_warning": "Output size and speed depend on the file. Incompatible streams cannot be remuxed without re-encoding.",
    "remux_warning": "MP4 requires compatible codecs. WEBM support is not guaranteed; transcoding may be needed.",
    "wrong_source": "You chose {source}, but this file ends with {actual}. Go back and select the correct source format.",
    "pcm_hint": "Audio becomes PCM in MOV; video is copied if its codec is compatible.",
    "remove_hint": "Audio will be removed; no additional settings are needed.",
    "no_size_guarantee": "25 MB is a target with headroom. Check the actual size after processing.",
})


def _storage():
    try:
        from config_storage import get_config_path, load_hardware_specs, save_hardware_specs
        return Path(get_config_path()), load_hardware_specs, save_hardware_specs
    except ImportError:
        path = BASE / "pc_specs.json"

        def read():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None

        def write(value):
            atomic_json(path, value)

        return path, read, write


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def load_config():
    value = _storage()[1]()
    return value if isinstance(value, dict) else None


def profile_storage_path(config_data=None):
    if isinstance(config_data, dict) and config_data.get("profile_path"):
        return Path(config_data["profile_path"]).expanduser()
    return _storage()[0].parent / "ffclass_profile.json"


def encoding_settings_path(config_data=None):
    return _storage()[0].parent / "settings.json"


def read_json(path):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def hardware_data():
    result = {"os": platform.platform(), "cpu": platform.processor() or "CPU", "gpu": "—", "rec": "libx264"}
    try:
        from oscheck import get_full_system_info
        scanned = get_full_system_info() or {}
        if isinstance(scanned, dict):
            result.update({k: v for k, v in scanned.items() if v is not None})
    except Exception:
        pass
    try:
        import psutil
        result["ram_gb"] = round(psutil.virtual_memory().total / 1024**3, 1)
    except ImportError:
        pass
    return result


class ScanSignals(QObject):
    done = Signal(dict)


DARK = """
QWidget { background:#101827; color:#ecf1f8; font:13px 'Segoe UI'; }
QLabel { background:transparent; }
QFrame#sidebar { background:#151f30; border-right:1px solid #29374a; }
QFrame#card { background:#1a2638; border:1px solid #314158; border-radius:12px; }
QLabel#title { font-size:23px; font-weight:700; }
QLabel#muted { color:#a9b8cb; }
QPushButton { background:#26364c; border:1px solid #394d66; border-radius:8px; padding:10px 14px; text-align:center; }
QPushButton:hover { background:#30445e; }
QPushButton:disabled { color:#8492a4; background:#202c3c; }
QPushButton#primary { background:#2879e4; border-color:#2879e4; color:white; font-weight:600; }
QPushButton#primary:hover { background:#1867d2; }
QPushButton#nav { text-align:left; background:transparent; border:0; padding:11px 14px; }
QPushButton#nav:hover { background:#24354a; }
QPushButton#nav[active="true"] { background:#243d60; color:#8fc3ff; }
QLineEdit,QComboBox,QListWidget { background:#101b2b; border:1px solid #394d66; border-radius:8px; padding:8px; min-height:20px; }
QComboBox::drop-down { border:0; width:26px; }
QComboBox QAbstractItemView { background:#172437; color:#edf3fa; selection-background-color:#2879e4; }
QProgressBar { background:#26364c; border:0; border-radius:5px; height:11px; text-align:center; }
QProgressBar::chunk { background:#2879e4; border-radius:5px; }
QScrollArea { border:0; }
"""
LIGHT = """
QWidget { background:#f5f7fa; color:#172437; font:13px 'Segoe UI'; }
QLabel { background:transparent; }
QFrame#sidebar { background:#fff; border-right:1px solid #e0e6ee; }
QFrame#card { background:#fff; border:1px solid #e0e6ee; border-radius:12px; }
QLabel#title { font-size:23px; font-weight:700; }
QLabel#muted { color:#536174; }
QPushButton { background:#fff; color:#172437; border:1px solid #d3dce8; border-radius:8px; padding:10px 14px; text-align:center; }
QPushButton:hover { background:#eef3f9; }
QPushButton:disabled { color:#788799; background:#edf0f4; }
QPushButton#primary { background:#2879e4; border-color:#2879e4; color:white; font-weight:600; }
QPushButton#primary:hover { background:#1867d2; }
QPushButton#nav { text-align:left; background:transparent; border:0; padding:11px 14px; }
QPushButton#nav:hover { background:#edf3fa; }
QPushButton#nav[active="true"] { background:#e8f1ff; color:#176bd0; }
QLineEdit,QComboBox,QListWidget { background:#fff; color:#172437; border:1px solid #d3dce8; border-radius:8px; padding:8px; min-height:20px; }
QComboBox::drop-down { border:0; width:26px; }
QComboBox QAbstractItemView { background:#fff; color:#172437; selection-background-color:#dbeafe; }
QProgressBar { background:#e4ebf4; border:0; border-radius:5px; height:11px; text-align:center; }
QProgressBar::chunk { background:#2879e4; border-radius:5px; }
QScrollArea { border:0; }
"""


def label(text, muted=False):
    item = QLabel(text)
    item.setWordWrap(True)
    if muted:
        item.setObjectName("muted")
    return item


def card():
    container = QFrame()
    container.setObjectName("card")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(20, 19, 20, 19)
    layout.setSpacing(13)
    return container, layout


def button(text, callback, primary=False):
    result = QPushButton(text)
    if primary:
        result.setObjectName("primary")
    result.clicked.connect(callback)
    return result


class MainWindow(QMainWindow):
    def __init__(self, config_data=None):
        super().__init__()
        self.setWindowTitle("FFClass")
        self.resize(940, 660)
        self.setMinimumSize(670, 510)
        self.setAcceptDrops(True)
        icon = BASE / "FFClass.png"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self.config = config_data if isinstance(config_data, dict) else (load_config() or {})
        self.profile_path = profile_storage_path(self.config)
        self.profile = read_json(self.profile_path)
        self.profile.setdefault("display_name", "User")
        self.profile.setdefault("theme", "dark")
        self.profile.setdefault("language", "RU")
        if self.profile["language"] not in TEXT:
            self.profile["language"] = "RU"
        self.preferences = read_json(encoding_settings_path(self.config))
        self.history = self.preferences.get("recent_files", [])
        if not isinstance(self.history, list):
            self.history = []
        self.info = None
        self.selected_goal = "archive"
        self._busy = False
        self._scan_signals = ScanSignals(self)
        self._scan_signals.done.connect(self._scan_finished)
        self._build_shell()
        self.apply_theme()
        self.retranslate()
        if self.config.get("setup_complete") and isinstance(self.config.get("hardware"), dict):
            self.show_dashboard()
        else:
            self.show_setup()

    def _build_shell(self):
        self.root = QStackedWidget()
        self.setCentralWidget(self.root)
        self.setup_view = self._build_setup()
        self.dashboard_view = self._build_dashboard()
        self.root.addWidget(self.setup_view)
        self.root.addWidget(self.dashboard_view)

    def _build_setup(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(30, 30, 30, 30)
        outer.addStretch()
        box, content = card()
        box.setMinimumWidth(450)
        box.setMaximumWidth(590)
        content.setContentsMargins(30, 30, 30, 30)
        content.setSpacing(20)
        self.setup_title = label("")
        self.setup_title.setObjectName("title")
        content.addWidget(self.setup_title)
        self.setup_hint = label("", True)
        content.addWidget(self.setup_hint)
        form = QFormLayout()
        form.setSpacing(18)
        self.setup_name = QLineEdit(self.profile.get("display_name", "User"))
        self.setup_name.setMaxLength(32)
        self.setup_name.setPlaceholderText("User")
        self.setup_name_label = QLabel()
        form.addRow(self.setup_name_label, self.setup_name)
        self.setup_language = QComboBox()
        self.setup_language.addItem("Русский", "RU")
        self.setup_language.addItem("English", "EN")
        self.setup_language.setCurrentIndex(1 if self.profile["language"] == "EN" else 0)
        self.setup_language.currentIndexChanged.connect(self._preview_language)
        self.setup_language_label = QLabel()
        form.addRow(self.setup_language_label, self.setup_language)
        self.setup_theme = QComboBox()
        self.setup_theme.addItem("", "dark")
        self.setup_theme.addItem("", "light")
        self.setup_theme.setCurrentIndex(1 if self.profile.get("theme") == "light" else 0)
        self.setup_theme.currentIndexChanged.connect(lambda: self._preview_theme())
        self.setup_theme_label = QLabel()
        form.addRow(self.setup_theme_label, self.setup_theme)
        content.addLayout(form)
        self.setup_status = label("", True)
        content.addWidget(self.setup_status)
        self.setup_progress = QProgressBar()
        self.setup_progress.setRange(0, 0)
        self.setup_progress.hide()
        content.addWidget(self.setup_progress)
        self.setup_button = button("", self.start_setup_scan, True)
        content.addWidget(self.setup_button)
        outer.addWidget(box, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()
        return page

    def _build_dashboard(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(194)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 20, 12, 16)
        side.setSpacing(6)
        brand = label("FFClass")
        brand.setObjectName("title")
        side.addWidget(brand)
        self.profile_button = button(self.profile.get("display_name") or "User", self.edit_profile)
        side.addWidget(self.profile_button)
        side.addSpacing(17)
        self.nav = []
        for name in ("home", "files", "pc"):
            index = len(self.nav)
            item = button("", lambda checked=False, index=index: self.switch_page(index))
            item.setObjectName("nav")
            side.addWidget(item)
            self.nav.append(item)
        side.addStretch()
        self.theme_toggle = button("", self.toggle_theme)
        side.addWidget(self.theme_toggle)
        row.addWidget(sidebar)
        self.pages = QStackedWidget()
        row.addWidget(self.pages, 1)
        self.pages.addWidget(self._home_page())
        self.pages.addWidget(self._files_page())
        self.pages.addWidget(self._computer_page())
        self.pages.addWidget(self._wizard_page())
        self.switch_page(0)
        return page

    def _scroll_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(30, 27, 30, 27)
        layout.setSpacing(18)
        scroll.setWidget(body)
        return scroll, layout

    def _home_page(self):
        page, layout = self._scroll_page()
        self.home_title = label("")
        self.home_title.setObjectName("title")
        layout.addWidget(self.home_title)
        self.home_hint = label("", True)
        layout.addWidget(self.home_hint)
        zone, z = card()
        self.video_title = label("")
        z.addWidget(self.video_title)
        self.file_label = label("", True)
        z.addWidget(self.file_label)
        self.choose_button = button("", self.choose_file, True)
        z.addWidget(self.choose_button)
        layout.addWidget(zone)
        layout.addStretch()
        return page

    def _wizard_page(self):
        page, layout = self._scroll_page()
        header = QHBoxLayout()
        self.wizard_title = label("")
        self.wizard_title.setObjectName("title")
        header.addWidget(self.wizard_title, 1)
        self.wizard_close = button("", lambda: self.switch_page(0))
        header.addWidget(self.wizard_close)
        layout.addLayout(header)
        self.wizard_file = label("", True)
        layout.addWidget(self.wizard_file)
        self.wizard_steps = label("", True)
        layout.addWidget(self.wizard_steps)
        self.wizard_stack = QStackedWidget()
        layout.addWidget(self.wizard_stack)

        # Stage 0: choose one real-life task.
        first, one = card()
        self.task_title = label("")
        self.task_title.setObjectName("title")
        one.addWidget(self.task_title)
        self.task_hint = label("", True)
        one.addWidget(self.task_hint)
        self.goal = QComboBox()
        for key in ("compress_flow", "audio_flow", "remux_flow"):
            self.goal.addItem("", key)
        self.goal.currentIndexChanged.connect(self._goal_changed)
        one.addWidget(self.goal)
        self.goal_description = label("", True)
        one.addWidget(self.goal_description)
        self.wizard_next_0 = button("", self.wizard_next, True)
        one.addWidget(self.wizard_next_0)
        one.addStretch()
        self.wizard_stack.addWidget(first)

        # Stage 1: a question determined by the chosen task.
        second, two = card()
        self.question_title = label("")
        self.question_title.setObjectName("title")
        two.addWidget(self.question_title)
        self.question_hint = label("", True)
        two.addWidget(self.question_hint)
        self.answer = QComboBox()
        self.answer.currentIndexChanged.connect(self._answer_changed)
        two.addWidget(self.answer)
        self.answer_note = label("", True)
        two.addWidget(self.answer_note)
        actions = QHBoxLayout()
        self.wizard_back_1 = button("", self.wizard_back)
        self.wizard_next_1 = button("", self.wizard_next, True)
        actions.addWidget(self.wizard_back_1)
        actions.addStretch()
        actions.addWidget(self.wizard_next_1)
        two.addLayout(actions)
        two.addStretch()
        self.wizard_stack.addWidget(second)

        # Stage 2: format, channels, priority and optional advanced fields.
        third, three = card()
        self.details_title = label("")
        self.details_title.setObjectName("title")
        three.addWidget(self.details_title)
        self.detail_note = label("", True)
        three.addWidget(self.detail_note)
        self.format_label = label("")
        three.addWidget(self.format_label)
        self.output_format = QComboBox()
        three.addWidget(self.output_format)
        self.channels_label = label("")
        three.addWidget(self.channels_label)
        self.channels = QComboBox()
        self.channels.addItem("", "source")
        self.channels.addItem("", "stereo")
        three.addWidget(self.channels)
        self.priority_label = label("")
        three.addWidget(self.priority_label)
        self.priority = QComboBox()
        self.priority.addItem("", "speed")
        self.priority.addItem("", "quality")
        three.addWidget(self.priority)
        self.video_settings = QWidget()
        settings = QVBoxLayout(self.video_settings)
        settings.setContentsMargins(0, 0, 0, 0)
        self.resolution_label = label("")
        settings.addWidget(self.resolution_label)
        self.resolution = QComboBox()
        for value in ("original", "1080", "720"):
            self.resolution.addItem("", value)
        settings.addWidget(self.resolution)
        three.addWidget(self.video_settings)
        self.advanced_button = button("", self.toggle_advanced)
        three.addWidget(self.advanced_button)
        self.advanced_panel = QWidget()
        advanced = QFormLayout(self.advanced_panel)
        advanced.setContentsMargins(0, 0, 0, 0)
        self.fps_label = QLabel()
        self.fps = QComboBox()
        for value in ("original", "24", "30", "60"):
            self.fps.addItem("", value)
        advanced.addRow(self.fps_label, self.fps)
        self.codec_label = QLabel()
        self.codec = QComboBox()
        for value in ("auto", "libx264", "libx265"):
            self.codec.addItem("", value)
        advanced.addRow(self.codec_label, self.codec)
        self.trim_start_label = QLabel()
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setRange(0, 999999)
        advanced.addRow(self.trim_start_label, self.trim_start)
        self.trim_end_label = QLabel()
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setRange(0, 999999)
        advanced.addRow(self.trim_end_label, self.trim_end)
        self.advanced_panel.hide()
        three.addWidget(self.advanced_panel)
        actions = QHBoxLayout()
        self.wizard_back_2 = button("", self.wizard_back)
        self.wizard_next_2 = button("", self.wizard_next, True)
        actions.addWidget(self.wizard_back_2)
        actions.addStretch()
        actions.addWidget(self.wizard_next_2)
        three.addLayout(actions)
        three.addStretch()
        self.wizard_stack.addWidget(third)

        # Stage 3: summary and action. Progress replaces the summary in-place.
        final, four = card()
        self.summary_title = label("")
        self.summary_title.setObjectName("title")
        four.addWidget(self.summary_title)
        self.summary = label("", True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        four.addWidget(self.summary)
        self.summary_warning = label("", True)
        four.addWidget(self.summary_warning)
        self.progress_card = QWidget()
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.status = label("", True)
        progress_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        progress_layout.addWidget(self.progress)
        self.cancel_button = button("", self.cancel_encoding)
        progress_layout.addWidget(self.cancel_button)
        self.progress_card.hide()
        four.addWidget(self.progress_card)
        actions = QHBoxLayout()
        self.wizard_back_3 = button("", self.wizard_back)
        self.start_button = button("", self.start_encoding, True)
        actions.addWidget(self.wizard_back_3)
        actions.addStretch()
        actions.addWidget(self.start_button)
        four.addLayout(actions)
        four.addStretch()
        self.wizard_stack.addWidget(final)
        layout.addStretch()
        return page

    def _files_page(self):
        page, layout = self._scroll_page()
        self.files_title = label("")
        self.files_title.setObjectName("title")
        layout.addWidget(self.files_title)
        self.files_hint = label("", True)
        layout.addWidget(self.files_hint)
        self.files_list = QListWidget()
        self.files_list.setMinimumHeight(220)
        layout.addWidget(self.files_list)
        self.open_folder_button = button("", self.open_output_folder)
        layout.addWidget(self.open_folder_button)
        layout.addStretch()
        self.update_history()
        return page

    def _computer_page(self):
        page, layout = self._scroll_page()
        self.pc_title = label("")
        self.pc_title.setObjectName("title")
        layout.addWidget(self.pc_title)
        info, details = card()
        self.pc_labels = {}
        self.pc_captions = {}
        for key, caption in (("os", "Система"), ("cpu", "Процессор"), ("gpu", "Графика"), ("ram_gb", "Память"), ("rec", "Кодировщик")):
            text = label("")
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            caption_label = label("", True)
            details.addWidget(caption_label)
            details.addWidget(text)
            self.pc_labels[key] = text
            self.pc_captions[key] = caption_label
        layout.addWidget(info)
        self.refresh_button = button("", self.refresh_pc)
        layout.addWidget(self.refresh_button)
        layout.addStretch()
        self.update_pc()
        return page

    def apply_theme(self):
        self.setStyleSheet(LIGHT if self.profile.get("theme") == "light" else DARK)

    def toggle_theme(self):
        self.profile["theme"] = "light" if self.profile.get("theme") != "light" else "dark"
        self.setup_theme.setCurrentIndex(1 if self.profile["theme"] == "light" else 0)
        self.apply_theme()
        self.retranslate()
        try:
            atomic_json(self.profile_path, self.profile)
        except OSError as exc:
            QMessageBox.warning(self, "FFClass", str(exc))

    def tr(self, key):
        return TEXT[self.profile["language"]][key]

    def retranslate(self):
        t = self.tr
        self.setup_title.setText(t("welcome"))
        self.setup_hint.setText(t("setup_hint"))
        self.setup_name_label.setText(t("name"))
        self.setup_language_label.setText(t("language"))
        self.setup_theme_label.setText(t("theme"))
        self.setup_theme.setItemText(0, t("dark"))
        self.setup_theme.setItemText(1, t("light"))
        if not self.setup_progress.isVisible():
            self.setup_status.setText(t("not_scanned"))
        self.setup_button.setText(t("continue"))
        for item, key in zip(self.nav, ("home", "files", "pc")):
            item.setText(t(key))
        self.home_title.setText(t("home"))
        self.home_hint.setText(t("home_hint"))
        self.video_title.setText(t("video"))
        if self.info is None:
            self.file_label.setText(t("no_file"))
        self.choose_button.setText(t("choose"))
        self.theme_toggle.setText(t("theme") + ": " + (t("light") if self.profile.get("theme") == "light" else t("dark")))
        self.wizard_title.setText(t("wizard"))
        self.wizard_close.setText(t("close_wizard"))
        self.task_title.setText(t("task"))
        self.task_hint.setText(t("task_hint"))
        for index, key in enumerate(("compress_flow", "audio_flow", "remux_flow")):
            self.goal.setItemText(index, t(key))
        self.question_hint.setText(t("question_hint"))
        self.wizard_next_0.setText(t("next"))
        self.wizard_next_1.setText(t("next"))
        self.wizard_next_2.setText(t("next"))
        for back_button in (self.wizard_back_1, self.wizard_back_2, self.wizard_back_3):
            back_button.setText(t("back"))
        self.summary_title.setText(t("summary_title"))
        self.format_label.setText(t("format_video"))
        self.channels_label.setText(t("channels"))
        self.channels.setItemText(0, t("source_channels"))
        self.channels.setItemText(1, t("stereo_channels"))
        self.priority_label.setText(t("priority"))
        self.priority.setItemText(0, t("speed"))
        self.priority.setItemText(1, t("max_quality"))
        self.resolution_label.setText(t("resolution"))
        for index, value in enumerate(("original", "1080", "720")):
            self.resolution.setItemText(index, t("original") if value == "original" else value + "p")
        self.advanced_button.setText(t("advanced"))
        for widget, key in ((self.fps_label, "fps"), (self.codec_label, "codec"),
                            (self.trim_start_label, "trim_start"), (self.trim_end_label, "trim_end")):
            widget.setText(t(key))
        self.fps.setItemText(0, t("original"))
        self.codec.setItemText(0, t("auto"))
        self._goal_changed()
        self._render_wizard()
        self.start_button.setText(t("start"))
        self.cancel_button.setText(t("cancel"))
        if not self._busy:
            self.status.setText(t("preparing"))
        self.files_title.setText(t("files"))
        self.files_hint.setText(t("files_hint"))
        self.open_folder_button.setText(t("open_folder"))
        self.pc_title.setText(t("pc"))
        self.refresh_button.setText(t("refresh"))
        for key, item in self.pc_captions.items():
            item.setText(t(key))
        self.update_history()

    def _preview_language(self):
        self.profile["language"] = self.setup_language.currentData()
        self.retranslate()

    def toggle_advanced(self):
        self.advanced_panel.setVisible(not self.advanced_panel.isVisible())

    def _preview_theme(self):
        self.profile["theme"] = self.setup_theme.currentData()
        self.apply_theme()

    def show_setup(self):
        self.root.setCurrentWidget(self.setup_view)

    def show_dashboard(self):
        self.root.setCurrentWidget(self.dashboard_view)
        self.update_pc()
        self.update_history()
        if not hasattr(self, "engine"):
            self.config["language"] = self.profile["language"]
            self._engine_timer = QTimer(self)
            self._engine_timer.setInterval(1000)
            self.engine = MediaEngine(self.config, self._engine_timer, self)
            self.engine.videoSelected.connect(self.video_ready)
            self.engine.processingProgress.connect(self.encoding_progress)
            self.engine.processingFinished.connect(self.encoding_finished)
            self.engine.processingError.connect(self.encoding_error)

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        for number, item in enumerate(self.nav):
            item.setProperty("active", number == index)
            item.style().unpolish(item)
            item.style().polish(item)

    def start_setup_scan(self):
        name = self.setup_name.text().strip() or "User"
        self.profile["display_name"] = name
        self.profile["theme"] = self.setup_theme.currentData()
        self.profile["language"] = self.setup_language.currentData()
        self.setup_button.setEnabled(False)
        self.setup_status.setText(self.tr("scanning"))
        self.setup_progress.show()
        threading.Thread(target=lambda: self._scan_signals.done.emit(hardware_data()), daemon=True).start()

    def _scan_finished(self, hardware):
        self.setup_progress.hide()
        self.setup_button.setEnabled(True)
        try:
            self.config["hardware"] = hardware
            self.config["setup_complete"] = True
            _storage()[2](self.config)
            atomic_json(self.profile_path, self.profile)
        except OSError as exc:
            self.setup_status.setText(f"Не удалось сохранить настройки: {exc}")
            return
        self.profile_button.setText(self.profile["display_name"])
        self.config["language"] = self.profile["language"]
        self.show_dashboard()

    def refresh_pc(self):
        self._scan_signals.done.disconnect(self._scan_finished)
        self._scan_signals.done.connect(self._pc_refreshed)
        threading.Thread(target=lambda: self._scan_signals.done.emit(hardware_data()), daemon=True).start()

    def _pc_refreshed(self, hardware):
        try:
            self.config["hardware"] = hardware
            _storage()[2](self.config)
        except OSError as exc:
            QMessageBox.warning(self, "FFClass", str(exc))
        self.update_pc()
        self._scan_signals.done.disconnect(self._pc_refreshed)
        self._scan_signals.done.connect(self._scan_finished)

    def update_pc(self):
        data = self.config.get("hardware") or {}
        for key, target in self.pc_labels.items():
            value = data.get(key, "—")
            if key == "ram_gb" and value != "—":
                value = f"{value} ГБ"
            target.setText(str(value))

    def edit_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("profile"))
        form = QFormLayout(dialog)
        name = QLineEdit(self.profile.get("display_name", "User"))
        name.setMaxLength(32)
        form.addRow(self.tr("profile_name"), name)
        language = QComboBox()
        language.addItem("Русский", "RU")
        language.addItem("English", "EN")
        language.setCurrentIndex(1 if self.profile["language"] == "EN" else 0)
        form.addRow(self.tr("language"), language)
        theme = QComboBox()
        theme.addItem(self.tr("dark"), "dark")
        theme.addItem(self.tr("light"), "light")
        theme.setCurrentIndex(1 if self.profile.get("theme") == "light" else 0)
        form.addRow(self.tr("theme"), theme)
        form.addRow(button(self.tr("save"), dialog.accept, True))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.profile["display_name"] = name.text().strip() or "User"
            self.profile["theme"] = theme.currentData()
            self.profile["language"] = language.currentData()
            try:
                atomic_json(self.profile_path, self.profile)
            except OSError as exc:
                QMessageBox.warning(self, "FFClass", str(exc))
                return
            self.profile_button.setText(self.profile["display_name"])
            self.setup_language.setCurrentIndex(language.currentIndex())
            self.config["language"] = self.profile["language"]
            self.apply_theme()
            self.retranslate()

    def dragEnterEvent(self, event):
        if hasattr(self, "engine") and event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not hasattr(self, "engine"):
            return
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.engine.selectVideoPath(url.toLocalFile())
                event.acceptProposedAction()
                return

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("select_dialog"), "", "Video (*.mp4 *.mkv *.mov *.avi *.webm *.m4v)")
        if path:
            self.file_label.setText(self.tr("reading"))
            self.engine.selectVideoPath(path)

    def video_ready(self, payload):
        self.info = json.loads(payload)
        info = self.info
        description = f"{info['name']}  ·  {info['size_label']}  ·  {info['resolution']}  ·  {info['duration_label']}"
        self.file_label.setText(description)
        self.wizard_file.setText(description)
        self.progress_card.hide()
        self.start_button.setEnabled(True)
        saved = self.preferences.get("last_options", {})
        task = saved.get("task", "compress_flow") if isinstance(saved, dict) else "compress_flow"
        self.goal.setCurrentIndex(max(0, self.goal.findData(task)))
        self._goal_changed()
        self.wizard_stack.setCurrentIndex(0)
        self._render_wizard()
        self.switch_page(3)

    def _goal_changed(self):
        flow = self.goal.currentData()
        if not flow:
            return
        t = self.tr
        self.goal_description.setText(t(flow + "_hint"))
        previous = self.answer.currentData()
        self.answer.blockSignals(True)
        self.answer.clear()
        keys = {"compress_flow": ("discord", "telegram", "disk"),
                "audio_flow": ("davinci", "change_audio", "remove_audio"),
                "remux_flow": ("mkv_source", "mov_source", "webm_source")}[flow]
        for key in keys:
            self.answer.addItem(t(key), key)
        index = self.answer.findData(previous)
        if index >= 0:
            self.answer.setCurrentIndex(index)
        self.answer.blockSignals(False)
        self._answer_changed()

    def _answer_changed(self):
        flow = self.goal.currentData()
        answer = self.answer.currentData()
        if not flow or not answer:
            return
        t = self.tr
        self.question_title.setText(t({"compress_flow": "compress_question", "audio_flow": "audio_question", "remux_flow": "remux_question"}[flow]))
        self.question_hint.setText(t("question_hint"))
        self.details_title.setText(t({"compress_flow": "compress_details", "audio_flow": "audio_details", "remux_flow": "remux_details"}[flow]))
        self.detail_note.setText(t({"compress_flow": "compress_detail_hint", "audio_flow": "audio_detail_hint", "remux_flow": "remux_detail_hint"}[flow]))
        self.answer_note.setText(t("no_size_guarantee") if answer == "discord" else
                                 t("pcm_hint") if answer == "davinci" else
                                 t("remove_hint") if answer == "remove_audio" else
                                 t("remux_warning") if flow == "remux_flow" else "")
        previous = self.output_format.currentData()
        self.output_format.clear()
        if flow == "audio_flow":
            formats = [("PCM / WAV", "pcm"), ("MP3", "mp3"), ("AAC", "aac"), ("FLAC", "flac")]
        else:
            formats = [("MP4", "mp4")] if flow == "remux_flow" else [("MP4", "mp4"), ("MKV", "mkv")]
        for name, value in formats:
            self.output_format.addItem(name, value)
        self.format_label.setText(t("format_audio") if flow == "audio_flow" else t("format_video"))
        requested = "pcm" if answer == "davinci" else previous
        index = self.output_format.findData(requested)
        if index >= 0:
            self.output_format.setCurrentIndex(index)
        self.output_format.setEnabled(answer not in {"davinci", "remove_audio"})
        self.format_label.setVisible(flow != "remux_flow" and answer != "remove_audio")
        self.output_format.setVisible(flow != "remux_flow" and answer != "remove_audio")
        self.channels_label.setVisible(flow == "audio_flow" and answer != "remove_audio")
        self.channels.setVisible(flow == "audio_flow" and answer != "remove_audio")
        self.priority_label.setVisible(flow == "compress_flow")
        self.priority.setVisible(flow == "compress_flow")
        self.video_settings.setVisible(flow == "compress_flow")
        self.advanced_button.setVisible(flow == "compress_flow")
        if flow != "compress_flow":
            self.advanced_panel.hide()
        self._render_summary()

    def _render_wizard(self):
        flow = self.goal.currentData()
        index = self.wizard_stack.currentIndex()
        count = 3 if flow == "remux_flow" or (flow == "audio_flow" and self.answer.currentData() == "remove_audio") else 4
        shown = min(index + 1, count)
        self.wizard_steps.setText(self.tr("step_indicator").format(step=shown, total=count))
        if index == 3:
            self._render_summary()

    def wizard_next(self):
        index = self.wizard_stack.currentIndex()
        flow = self.goal.currentData()
        answer = self.answer.currentData()
        skip_details = flow == "remux_flow" or (flow == "audio_flow" and answer == "remove_audio")
        self.wizard_stack.setCurrentIndex(3 if index == 1 and skip_details else min(3, index + 1))
        self._render_wizard()

    def wizard_back(self):
        index = self.wizard_stack.currentIndex()
        flow = self.goal.currentData()
        answer = self.answer.currentData()
        skip_details = flow == "remux_flow" or (flow == "audio_flow" and answer == "remove_audio")
        self.wizard_stack.setCurrentIndex(1 if index == 3 and skip_details else max(0, index - 1))
        self._render_wizard()

    def _render_summary(self):
        if not self.info:
            return
        flow = self.goal.currentData()
        answer = self.answer.currentData()
        t = self.tr
        lines = [self.info["name"], t(flow), t(answer)]
        warning = ""
        valid = True
        if flow == "compress_flow":
            lines += [t("priority") + ": " + self.priority.currentText(),
                      t("format_video") + ": " + self.output_format.currentText(),
                      t("resolution") + ": " + self.resolution.currentText()]
            if answer == "discord":
                warning = t("no_size_guarantee")
        elif flow == "audio_flow":
            if answer != "remove_audio":
                lines += [t("format_audio") + ": " + self.output_format.currentText(),
                          t("channels") + ": " + self.channels.currentText()]
            if answer == "davinci":
                warning = t("pcm_hint")
        else:
            expected = {"mkv_source": ".mkv", "mov_source": ".mov", "webm_source": ".webm"}[answer]
            actual = Path(self.info["path"]).suffix.lower()
            valid = expected == actual
            warning = t("remux_warning") if valid else t("wrong_source").format(source=expected.upper(), actual=actual.upper())
        self.summary.setText("\n".join(lines))
        self.summary_warning.setText(warning)
        self.start_button.setEnabled(valid and not self._busy)

    def start_encoding(self):
        if not self.info or self._busy or not self.start_button.isEnabled():
            return
        flow = self.goal.currentData()
        answer = self.answer.currentData()
        fmt = self.output_format.currentData()
        if flow == "compress_flow":
            options = {"goal": "send" if answer == "discord" else "archive",
                       "preset": "fast" if self.priority.currentData() == "speed" else "quality",
                       "resolution": self.resolution.currentData(), "container": fmt}
            if answer == "discord":
                options["target_size_mb"] = 25
            if self.priority.currentData() == "quality":
                options["video_codec"] = "libx264"
            if not self.advanced_panel.isHidden():
                options["fps"] = self.fps.currentData()
                if self.codec.currentData() != "auto":
                    options["video_codec"] = self.codec.currentData()
                if self.trim_start.value() > 0:
                    options["trim_start"] = self.trim_start.value()
                if self.trim_end.value() > 0:
                    options["trim_end"] = self.trim_end.value()
        elif flow == "audio_flow":
            options = {"goal": "repair_audio", "audio_action":
                       "fix" if answer == "davinci" else "remove" if answer == "remove_audio" else "convert",
                       "audio_format": "pcm" if answer == "davinci" else fmt if answer == "change_audio" else "aac",
                       "audio_channels": self.channels.currentData()}
        else:
            options = {"goal": "remux", "container": "mp4"}
        self.preferences["last_options"] = {"task": flow, "answer": answer, "format": fmt}
        try:
            atomic_json(encoding_settings_path(self.config), self.preferences)
        except OSError:
            pass
        self._busy = True
        self.start_button.setEnabled(False)
        self.wizard_back_3.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText(self.tr("starting"))
        self.progress_card.show()
        self.engine.startEncoding(json.dumps(options))

    def encoding_progress(self, payload):
        info = json.loads(payload)
        self.progress.setValue(int(float(info.get("percent") or 0)))
        self.status.setText(f"{self.progress.value()}%  ·  {self.tr('remaining')}: {info.get('eta', '—')}")

    def encoding_finished(self, payload):
        self._busy = False
        self.start_button.setEnabled(True)
        self.wizard_back_3.setEnabled(True)
        result = json.loads(payload)
        if result.get("cancelled"):
            self.status.setText(self.tr("cancelled"))
            return
        path = result.get("output_path", "")
        self.status.setText(self.tr("done") + result.get("output_name", ""))
        self.progress.setValue(100)
        if path:
            self.history = [path] + [p for p in self.history if p != path]
            self.history = self.history[:15]
            self.preferences["recent_files"] = self.history
            try:
                atomic_json(encoding_settings_path(self.config), self.preferences)
            except OSError:
                pass
            self.update_history()

    def encoding_error(self, message):
        self._busy = False
        self.start_button.setEnabled(True)
        self.wizard_back_3.setEnabled(True)
        self.progress_card.hide()
        self.status.setText(str(message))
        QMessageBox.warning(self, self.tr("error"), str(message))

    def cancel_encoding(self):
        self.engine.cancelEncoding()

    def update_history(self):
        self.files_list.clear()
        for path in self.history:
            self.files_list.addItem(path)
        if not self.history:
            self.files_list.addItem(self.tr("no_history"))

    def open_output_folder(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        row = self.files_list.currentRow()
        path = self.history[row] if 0 <= row < len(self.history) else (self.history[0] if self.history else "")
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


SetupWizardWindow = MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
