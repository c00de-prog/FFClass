"""FFClass: Модуль автоопределения системы (oscheck.py)"""

import platform
import subprocess
import sys
from hardware_db import Hardware, recommend_encoder


def _run_ps(command: str) -> str:
    """Выполняет команду PowerShell с явной установкой UTF-8 кодировки вывода."""
    ps_cmd = (
        f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"
    )
    cmd = ["powershell", "-NoProfile", "-Command", ps_cmd]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return output.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def get_clean_os_name() -> str:
    """Возвращает точное имя Windows (включая Windows 11) без искажения кодировки."""
    if sys.platform != "win32":
        return f"{platform.system()} {platform.release()}"

    # 1. Запрос точного названия через PowerShell с UTF-8
    output = _run_ps("(Get-CimInstance Win32_OperatingSystem).Caption")
    if output:
        return output.replace("Microsoft ", "").strip()

    # 2. Резервный метод через реестр Build Number
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        build, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
        winreg.CloseKey(key)

        if int(build) >= 22000:
            return "Windows 11"
        return "Windows 10"
    except Exception:
        return f"Windows {platform.release()}"


def get_clean_cpu_name() -> str:
    """Возвращает нормальное маркетинговое название процессора."""
    if sys.platform == "win32":
        output = _run_ps("(Get-CimInstance Win32_Processor).Name")
        if output:
            return output

    return platform.processor() or "Неизвестный процессор"


def get_gpu_names() -> list[str]:
    """Возвращает список установленных видеокарт (GPU)."""
    gpus = []
    if sys.platform == "win32":
        output = _run_ps("(Get-CimInstance Win32_VideoController).Name")
        if output:
            gpus = [g.strip() for g in output.splitlines() if g.strip()]

    return gpus or ["Неизвестная видеокарта"]


def get_full_system_info() -> dict:
    """Собирает всю информацию о системе и связывает её с hardware_db.py."""
    os_name = get_clean_os_name()
    cpu_name = get_clean_cpu_name()
    gpu_list = get_gpu_names()
    gpu_str = ", ".join(gpu_list)

    hw = Hardware.from_scanner(cpu_name=cpu_name, gpu_names=gpu_list)

    try:
        rec = recommend_encoder(hw, codec="h264", verify=False)
        if rec.mode == "hardware":
            rec_text = (
                f"⚡ Найдено железо ({rec.gpu_name}) -> Энкодер: {rec.encoder}"
            )
        else:
            rec_text = f"💻 Использование CPU -> Энкодер: {rec.encoder}"
    except Exception:
        rec_text = "💻 Кодирование через CPU (libx264)"

    return {
        "os": os_name,
        "cpu_cores": cpu_name,
        "gpu": gpu_str,
        "ffmpeg_encoder": rec_text,
    }