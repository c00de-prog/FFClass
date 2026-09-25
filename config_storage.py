import json
import os
import sys


def get_config_path() -> str:
    """Определяет путь для сохранения файла конфига.

    Работает и при запуске из исходного кода, и после сборки в .exe.
    """
    if getattr(sys, "frozen", False):
        # Если запущено как .exe, сохраняем в папку AppData пользователя
        base_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FFClass"
        )
    else:
        # Если запущено из .py, сохраняем в папке проекта
        base_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "pc_specs.json")


def save_hardware_specs(data: dict):
    """Сохраняет характеристики ПК в JSON файл."""
    filepath = get_config_path()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Данные ПК сохранены в: {filepath}")
    except Exception as e:
        print(f"Ошибка сохранения: {e}")


def load_hardware_specs() -> dict | None:
    """Загружает характеристики ПК из JSON файла, если он существует."""
    filepath = get_config_path()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
            return None
    return None