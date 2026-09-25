"""
FFClass: Модуль ручного ввода данных и связка с hardware_db.py
"""

from PySide6 import QtWidgets

# Импортируем функционал из вашего нового модуля hardware_db
from hardware_db import Hardware, recommend_encoder


def get_ffmpeg_hardware_recommendation(
    gpu_name: str, cpu_name: str = "", codec: str = "h264"
) -> str:
    """
    Определяет подходящий энкодер FFmpeg на основе базы данных hardware_db.
    """
    if not gpu_name and not cpu_name:
        return "💻 Данные не введены -> Кодирование через CPU (libx264)"

    # Формируем объект Hardware для базы данных
    gpus = [gpu_name] if gpu_name else []
    hw = Hardware.from_scanner(cpu_name=cpu_name, gpu_names=gpus)

    try:
        # Пробуем получить рекомендации из базы данных (без жесткой проверки FFmpeg в системе)
        rec = recommend_encoder(hw, codec=codec, verify=False)

        if rec.mode == "hardware":
            return f"⚡ Найдено железо ({rec.gpu_name}) -> Энкодер: {rec.encoder}"
        else:
            return f"💻 Использование CPU -> Энкодер: {rec.encoder}"

    except Exception:
        # Резервный вариант, если возникло исключение
        return "💻 Кодирование через CPU (libx264)"


class ManualInputDialog(QtWidgets.QDialog):
    """Диалоговое окно для ручного ввода характеристик ПК."""

    def __init__(self, parent=None, is_ru=True):
        super().__init__(parent)

        self.is_ru = is_ru
        self.setWindowTitle(
            "Ручной ввод комплектующих"
            if is_ru
            else "Manual Hardware Input"
        )
        self.setFixedSize(420, 230)

        # Поля ввода
        self.cpu_input = QtWidgets.QLineEdit()
        self.cpu_input.setPlaceholderText(
            "например: Intel Core i5-12400 или AMD Ryzen 5 5600"
            if is_ru
            else "e.g. Intel Core i5-12400 or AMD Ryzen 5 5600"
        )

        self.gpu_input = QtWidgets.QLineEdit()
        self.gpu_input.setPlaceholderText(
            "например: NVIDIA RTX 4060 или AMD Radeon RX 7600"
            if is_ru
            else "e.g. NVIDIA RTX 4060 or AMD Radeon RX 7600"
        )

        # Кнопки
        self.btn_save = QtWidgets.QPushButton("Сохранить" if is_ru else "Save")
        self.btn_cancel = QtWidgets.QPushButton(
            "Отмена" if is_ru else "Cancel"
        )

        # Layout формы
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(
            "Процессор (CPU):" if is_ru else "Processor (CPU):", self.cpu_input
        )
        form_layout.addRow(
            "Видеокарта (GPU):" if is_ru else "Graphics (GPU):", self.gpu_input
        )

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(15)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

        # Сигналы
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def get_data(self):
        """Возвращает введенные пользователем данные и рекомендацию из hardware_db."""
        cpu = self.cpu_input.text().strip() or "Не указан"
        gpu = self.gpu_input.text().strip() or "Не указана"

        recommendation = get_ffmpeg_hardware_recommendation(gpu, cpu)

        return {
            "os": "Указано вручную",
            "cpu": cpu,
            "gpu": gpu,
            "rec": recommendation,
        }