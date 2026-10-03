"""Cheap, on-demand system facts; no timers, FFmpeg or external processes."""

import ctypes
import os
import sys


def memory_total_gb():
    """Physical RAM using an OS API; return None when the API is unavailable."""
    if sys.platform == "win32":
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
    if precise and ("Core" in precise or "Ryzen" in precise or "Xeon" in precise):
        return precise
    return generic or precise or "CPU"
