import locale
import os
import sys
from PySide6 import QtCore, QtWidgets

# --- ИМПОРТ НАШИХ МОДУЛЕЙ ---
from config_storage import get_config_path, load_hardware_specs, save_hardware_specs
from custom_input import ManualInputDialog
from hardware_db import Hardware, recommend_encoder
from oscheck import get_full_system_info
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("FFClass")
        self.resize(700, 480)

        # Разрешаем Drag & Drop
        self.setAcceptDrops(True)
        
        self.setWindowIcon(QIcon("FFClass.png"))

        # Переменные состояния
        self.hardware_confirmed = False
        self.has_checked = False
        self.current_specs = None  # Данные о комплектующих
        self.current_step = 1  # Текущий шаг (1 или 2)

        # --- 1. ВЕРХНЯЯ ПАНЕЛЬ ---
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(
            ["Тёмная тема", "Светлая тема", "Киберпанк (Закат)"]
        )

        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItems(["Русский", "English"])

        self.btn_continue = QtWidgets.QPushButton("Продолжить ➔")
        self.btn_continue.setEnabled(False)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self.theme_combo)
        top_layout.addWidget(self.lang_combo)
        top_layout.addWidget(self.btn_continue)

        # --- 2. ЦЕНТРАЛЬНАЯ ОБЛАСТЬ ---
        self.label = QtWidgets.QLabel(
            "Перетащите сюда файл или нажмите «Проверить»"
        )
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)

        # --- 3. БЛОК ПОДТВЕРЖДЕНИЯ (Да / Нет) ---
        self.confirm_widget = QtWidgets.QWidget()
        self.confirm_label = QtWidgets.QLabel(
            "Информация о комплектующих верна?"
        )

        self.btn_yes = QtWidgets.QPushButton("Да ✔")
        self.btn_no = QtWidgets.QPushButton("Нет ✖")

        confirm_layout = QtWidgets.QHBoxLayout()
        confirm_layout.addWidget(self.confirm_label)
        confirm_layout.addWidget(self.btn_yes)
        confirm_layout.addWidget(self.btn_no)
        self.confirm_widget.setLayout(confirm_layout)
        self.confirm_widget.hide()

        # --- 4. НИЖНЯЯ ПАНЕЛЬ ---
        self.btn_check = QtWidgets.QPushButton("Проверить")

        # --- ОСНОВНАЯ КОМПОНОВКА ---
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.label, stretch=1)
        main_layout.addWidget(self.confirm_widget)
        main_layout.addWidget(self.btn_check)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- СИГНАЛЫ ---
        self.theme_combo.currentIndexChanged.connect(self.apply_theme)
        self.lang_combo.currentIndexChanged.connect(
            self.on_language_combo_change
        )
        self.btn_check.clicked.connect(self.start_checking_animation)
        self.btn_continue.clicked.connect(self.on_continue)
        self.btn_yes.clicked.connect(self.on_confirm_yes)
        self.btn_no.clicked.connect(self.on_confirm_no)

        # Автоопределение языка и темы
        self.detect_system_language()
        self.apply_theme()

        # ПРОВЕРКА ФАЙЛА КОНФИГУРАЦИИ ПРИ ЗАПУСКЕ
        self.check_saved_config()

    def check_saved_config(self):
        """Проверяет наличие файла конфигурации на диске при запуске."""
        config_file = get_config_path()

        # Если файла НЕТ — начинаем с Шага 1 (проверка ПК)
        if not os.path.exists(config_file):
            self.current_step = 1
            self.confirm_widget.hide()
            self.btn_check.show()
            self.btn_continue.show()
            self.btn_continue.setEnabled(False)
            self.update_ui_text()
            return

        # Если файл ЕСТЬ — пропускаем проверку и сразу идем на Шаг 2 (загрузка файлов)
        saved_specs = load_hardware_specs()
        if saved_specs:
            self.current_specs = saved_specs
            self.current_step = 2
            self.confirm_widget.hide()
            self.btn_check.hide()
            self.btn_continue.hide()
            self.render_step_2()

    # --- 🌐 Язык системы ---
    def detect_system_language(self):
        try:
            sys_lang, _ = locale.getdefaultlocale()
            if sys_lang and sys_lang.startswith("ru"):
                self.lang_combo.setCurrentText("Русский")
                self.current_lang = "RU"
            else:
                self.lang_combo.setCurrentText("English")
                self.current_lang = "EN"
        except Exception:
            self.lang_combo.setCurrentText("English")
            self.current_lang = "EN"

        self.update_ui_text()

    def on_language_combo_change(self):
        selected = self.lang_combo.currentText()
        self.current_lang = "RU" if selected == "Русский" else "EN"
        self.update_ui_text()

    def update_ui_text(self):
        if self.current_step == 2:
            self.render_step_2()
            return

        if self.current_lang == "RU":
            self.btn_continue.setText("Продолжить ➔")
            self.btn_check.setText("Проверить")
            self.confirm_label.setText("Информация о комплектующих верна?")
            self.btn_yes.setText("Да ✔")
            self.btn_no.setText("Нет ✖")

            if not self.has_checked:
                self.label.setText(
                    "Перетащите сюда файл или нажмите «Проверить»"
                )
        else:
            self.btn_continue.setText("Continue ➔")
            self.btn_check.setText("Check System")
            self.confirm_label.setText("Is the hardware information correct?")
            self.btn_yes.setText("Yes ✔")
            self.btn_no.setText("No ✖")

            if not self.has_checked:
                self.label.setText(
                    "Drag & drop a file here or click «Check System»"
                )

    # --- 🔍 АНИМАЦИЯ ПРОВЕРКИ (checking...) ---
    def start_checking_animation(self):
        self.confirm_widget.hide()
        self.btn_check.setEnabled(False)
        self.check_dots = 0

        self.check_timer = QtCore.QTimer(self)
        self.check_timer.timeout.connect(self.animate_checking)
        self.check_timer.start(120)

    def animate_checking(self):
        self.check_dots += 1
        dots = "." * (self.check_dots % 4)

        if self.current_lang == "RU":
            self.label.setText(f"Проверка{dots}")
        else:
            self.label.setText(f"checking{dots}")

        if self.check_dots >= 8:
            self.check_timer.stop()
            self.btn_check.setEnabled(True)
            self.run_hardware_check()

    def run_hardware_check(self):
        self.has_checked = True
        sys_data = get_full_system_info()

        gpus = [sys_data["gpu"]] if sys_data["gpu"] else []
        hw = Hardware.from_scanner(
            cpu_name=sys_data["cpu_cores"], gpu_names=gpus
        )

        try:
            rec = recommend_encoder(hw, codec="h264", verify=False)
            if rec.mode == "hardware":
                ffmpeg_rec = f"⚡ Ускорение ({rec.gpu_name}) -> {rec.encoder}"
            else:
                ffmpeg_rec = f"💻 Кодирование через CPU ({rec.encoder})"
        except Exception:
            ffmpeg_rec = "💻 Кодирование через CPU (libx264)"

        self.current_specs = {
            "os": sys_data["os"],
            "cpu": sys_data["cpu_cores"],
            "gpu": sys_data["gpu"],
            "rec": ffmpeg_rec,
        }

        if self.current_lang == "RU":
            text = (
                f"<b>Операционная система:</b> {sys_data['os']}<br><br>"
                f"<b>Процессор:</b> {sys_data['cpu_cores']}<br><br>"
                f"<b>Видеокарта (GPU):</b> {sys_data['gpu']}<br><br>"
                f"<b>Рекомендация для FFmpeg:</b><br>{ffmpeg_rec}"
            )
        else:
            text = (
                f"<b>OS:</b> {sys_data['os']}<br><br>"
                f"<b>CPU:</b> {sys_data['cpu_cores']}<br><br>"
                f"<b>GPU:</b> {sys_data['gpu']}<br><br>"
                f"<b>FFmpeg Recommendation:</b><br>{ffmpeg_rec}"
            )

        self.label.setText(text)
        self.hardware_confirmed = False
        self.btn_continue.setEnabled(False)
        self.confirm_widget.show()

    def on_confirm_yes(self):
        self.hardware_confirmed = True
        self.btn_continue.setEnabled(True)

        msg = (
            "✅ Данные подтверждены! Теперь вы можете нажать «Продолжить»."
            if self.current_lang == "RU"
            else "✅ Confirmed! You can now click «Continue»."
        )
        self.confirm_label.setText(msg)

    def on_confirm_no(self):
        dialog = ManualInputDialog(self, is_ru=(self.current_lang == "RU"))

        if dialog.exec():
            user_data = dialog.get_data()
            self.current_specs = user_data

            if self.current_lang == "RU":
                text = (
                    f"<b>Операционная система:</b> {user_data['os']}<br><br>"
                    f"<b>Процессор:</b> {user_data['cpu']}<br><br>"
                    f"<b>Видеокарта (GPU):</b> {user_data['gpu']}<br><br>"
                    f"<b>Рекомендация для FFmpeg:</b><br>{user_data['rec']}"
                )
            else:
                text = (
                    f"<b>OS:</b> {user_data['os']}<br><br>"
                    f"<b>CPU:</b> {user_data['cpu']}<br><br>"
                    f"<b>GPU:</b> {user_data['gpu']}<br><br>"
                    f"<b>FFmpeg Recommendation:</b><br>{user_data['rec']}"
                )

            self.label.setText(text)
            self.hardware_confirmed = True
            self.btn_continue.setEnabled(True)

            msg = (
                "✅ Данные введены вручную! Нажмите «Продолжить»."
                if self.current_lang == "RU"
                else "✅ Data entered manually! Click «Continue»."
            )
            self.confirm_label.setText(msg)

    # --- 🚀 АНИМАЦИЯ ПОДГОТОВКИ И СОХРАНЕНИЯ ---
    def on_continue(self):
        self.confirm_widget.hide()
        self.btn_check.hide()

        self.loading_stage = 0
        self.loading_dots = 0

        self.loading_timer = QtCore.QTimer(self)
        self.loading_timer.timeout.connect(self.animate_saving_and_transition)
        self.loading_timer.start(140)

    def animate_saving_and_transition(self):
        self.loading_dots += 1
        dots = "." * (self.loading_dots % 4)

        if self.loading_stage == 0:
            if self.current_lang == "RU":
                self.label.setText(f"⚙️ Подготовка к следующему шагу{dots}")
            else:
                self.label.setText(f"⚙️ Preparing for the next step{dots}")

            if self.loading_dots >= 6:
                self.loading_stage = 1
                self.loading_dots = 0

        elif self.loading_stage == 1:
            if self.current_lang == "RU":
                self.label.setText(f"💾 Сохранение конфигурации ПК{dots}")
            else:
                self.label.setText(f"💾 Saving PC configuration{dots}")

            if self.loading_dots >= 6:
                # Физическое сохранение данных в локальный файл JSON
                if self.current_specs:
                    save_hardware_specs(self.current_specs)

                self.loading_stage = 2
                self.loading_dots = 0

        elif self.loading_stage == 2:
            if self.current_lang == "RU":
                self.label.setText(f"🚀 Загрузка интерфейса{dots}")
            else:
                self.label.setText(f"🚀 Loading interface{dots}")

            if self.loading_dots >= 6:
                self.loading_timer.stop()
                self.btn_continue.hide()
                self.current_step = 2
                self.render_step_2()

    # --- 🎬 ШАГ 2: ЧИСТЫЙ ЭКРАН ЗАГРУЗКИ ФАЙЛОВ ---
    def render_step_2(self):
        """Отображает только окно перетаскивания файлов (без характеристик ПК)."""
        if self.current_lang == "RU":
            self.label.setText(
                "📁 <b>Загружайте Файлы</b><br><br>"
                "<i>Перетащите сюда файлы или видео для обработки</i>"
            )
        else:
            self.label.setText(
                "📁 <b>Upload Files</b><br><br>"
                "<i>Drag & drop files or video here to process</i>"
            )

    # --- ДРАГ-ЭНД-ДРОП ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = urls[0].toLocalFile()

        if not os.path.exists(file_path):
            self.label.setText("❌ Ошибка: Файл не найден")
            return

        if os.path.isdir(file_path):
            self.label.setText("❌ Ошибка: Скинута папка, а нужен файл")
            return

        self.label.setText(f"📁 Файл получен:\n{file_path}")

    # --- ТЕМЫ ОФОРМЛЕНИЯ ---
    def apply_theme(self):
        theme = self.theme_combo.currentText()

        if theme == "Тёмная тема":
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #121212; color: #ffffff; }
                QLabel { background-color: #1e1e1e; color: #e0e0e0; border: 2px dashed #444444; border-radius: 8px; padding: 12px; font-size: 14px; }
                QPushButton { background-color: #2b2b2b; color: #ffffff; border: 2px solid #555555; border-radius: 6px; padding: 10px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background-color: #3d3d3d; }
                QPushButton:disabled { background-color: #1a1a1a; color: #555555; border: 2px solid #333333; }
                QComboBox, QLineEdit { background-color: #1e1e1e; color: #ffffff; border: 2px solid #444444; border-radius: 6px; padding: 5px; font-weight: bold; }
            """)
        elif theme == "Светлая тема":
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #f8f9fa; color: #000000; }
                QLabel { background-color: #ffffff; color: #000000; border: 2px dashed #a0a0a0; border-radius: 8px; padding: 12px; font-size: 14px; }
                QPushButton { background-color: #ffffff; color: #000000; border: 2px solid #000000; border-radius: 6px; padding: 10px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background-color: #e2e2e2; }
                QPushButton:disabled { background-color: #f0f0f0; color: #aaa; border: 2px solid #ccc; }
                QComboBox, QLineEdit { background-color: #ffffff; color: #000000; border: 2px solid #000000; border-radius: 6px; padding: 5px; font-weight: bold; }
            """)
        elif theme == "Киберпанк (Закат)":
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #1a1a24; color: #f3f4f6; }
                QLabel { background-color: #242438; color: #f3f4f6; border: 2px dashed #6b7280; border-radius: 8px; padding: 12px; font-size: 14px; }
                QPushButton { background-color: #374151; color: #ffffff; border: 2px solid #4b5563; border-radius: 6px; padding: 10px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background-color: #4b5563; }
                QPushButton:disabled { background-color: #111827; color: #4b5563; border: 2px solid #1f2937; }
                QComboBox, QLineEdit { background-color: #242438; color: #f3f4f6; border: 2px solid #4b5563; border-radius: 6px; padding: 5px; font-weight: bold; }
            """)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())