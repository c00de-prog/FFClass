"""Cheap, on-demand system facts; no timers, FFmpeg or external processes."""

import ctypes
import os
import re
import sys


def memory_total_gb():
    """Installed RAM (rather than Windows usable RAM), without a subprocess."""
    if sys.platform == "win32":
        installed_kb = ctypes.c_ulonglong()
        try:
            if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(installed_kb)):
                return round(installed_kb.value / 1024 ** 2, 1)
        except (AttributeError, OSError):
            pass

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended", ctypes.c_ulonglong),
            ]

        value = MemoryStatus()
        value.length = ctypes.sizeof(value)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
                return round(value.total_phys / 1024 ** 3, 1)
        except (AttributeError, OSError):
            return None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * size / 1024 ** 3, 1)
    except (AttributeError, OSError, ValueError):
        return None


def recommended_cpu_name(data):
    precise = str(data.get("cpu_cores") or "").strip()
    generic = str(data.get("cpu") or "").strip()
    if precise and not _is_cpu_identifier(precise):
        return precise
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                name = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
                if name and not _is_cpu_identifier(name):
                    return " ".join(name.split())
        except (OSError, ImportError, ValueError):
            pass
    return generic or precise or "CPU"


def _is_cpu_identifier(value):
    text = value.casefold()
    return "family " in text and "model " in text and "stepping " in text


_ENCODER_NAMES = frozenset({
    "h264_nvenc", "hevc_nvenc", "av1_nvenc",
    "h264_qsv", "hevc_qsv", "av1_qsv",
    "h264_amf", "hevc_amf", "av1_amf",
    "libx264", "libx265", "libsvtav1", "libaom-av1",
})
_ENCODER_PATTERN = re.compile(
    r"(?<![\w-])(?:h264_nvenc|hevc_nvenc|av1_nvenc|"
    r"h264_qsv|hevc_qsv|av1_qsv|h264_amf|hevc_amf|av1_amf|"
    r"libx264|libx265|libsvtav1|libaom-av1)(?![\w-])", re.I,
)


def recommended_encoder_name(hardware):
    """Use the scanner's catalogue candidate before the old CPU default.

    This is an unverified recommendation. The encode job tries the candidate
    and can fall back to libx264 if the driver or FFmpeg rejects it.
    """
    hardware = hardware if isinstance(hardware, dict) else {}
    gpu = str(hardware.get("gpu") or "").strip().casefold()
    for field in ("ffmpeg_encoder", "rec"):
        match = _ENCODER_PATTERN.search(str(hardware.get(field) or ""))
        if not match:
            continue
        encoder = match.group(0).lower()
        if encoder not in _ENCODER_NAMES:
            continue
        if encoder.endswith(("_nvenc", "_qsv", "_amf")) and gpu in {
            "", "—", "none", "n/a", "unknown", "не определена",
        }:
            continue
        return encoder
    return "libx264"
