"""Build the portable FFClass app and release ZIP on Windows.

On the build machine only:
    python stage_ffmpeg.py --source C:\\tools\\ffmpeg\\bin
    python -m pip install -r requirements.txt -r requirements-build.txt
    python build_windows.py

Upload dist/FFClass-Windows.zip to GitHub Releases. It includes the app,
bundled FFmpeg, the removal command, and the quick-start instructions.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from stage_ffmpeg import verify_pair


PROJECT = Path(__file__).resolve().parent
BIN = PROJECT / "bin"
RELEASE_FILES = ("Remove FFClass.cmd", "remove_ffclass.ps1", "START_HERE.txt")


def build(make_zip=True):
    if sys.platform != "win32":
        raise RuntimeError("Windows EXE нужно собирать на Windows, используя Windows Python.")
    if not importlib.util.find_spec("PyInstaller"):
        raise RuntimeError("Для сборки установите PyInstaller в среду разработчика.")
    if not importlib.util.find_spec("PySide6"):
        raise RuntimeError("Для сборки установите PySide6 в среду разработчика.")
    for required in ("gui.py", "encoder.py", "resource_manager.py", "oscheck.py", "hardware_db.py", *RELEASE_FILES):
        if not (PROJECT / required).is_file():
            raise FileNotFoundError(f"Нет {required}: поместите файл в корень проекта до сборки.")
    ffmpeg, ffprobe = BIN / "ffmpeg.exe", BIN / "ffprobe.exe"
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise FileNotFoundError("Подготовьте проверенную пару через stage_ffmpeg.py --source <папка>.")
    version = verify_pair(ffmpeg, ffprobe)
    manifest = BIN / "ffclass_ffmpeg.json"
    if not manifest.is_file():
        raise RuntimeError("Папка bin не подготовлена stage_ffmpeg.py: отсутствует манифест.")
    import hashlib
    expected = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    for binary in (ffmpeg, ffprobe):
        if hashlib.sha256(binary.read_bytes()).hexdigest() != expected.get(binary.name):
            raise RuntimeError(f"Файл {binary.name} изменился после проверки. Повторите stage_ffmpeg.py.")

    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
            "--windowed", "--name", "FFClass", "--contents-directory", "_internal",
            "--exclude-module", "PySide6.QtWebEngineWidgets",
            "--exclude-module", "PySide6.QtWebEngineCore",
            "--exclude-module", "PySide6.QtWebChannel",
            "--hidden-import", "oscheck", "--hidden-import", "hardware_db"]
    for binary in (ffmpeg, ffprobe):
        args.extend(("--add-binary", f"{binary};bin"))
    args.extend(("--add-data", f"{manifest};bin"))
    logo = PROJECT / "FFClass.png"
    if logo.is_file():
        args.extend(("--add-data", f"{logo};."))
    icon = PROJECT / "FFClass.ico"
    if icon.is_file():
        args.extend(("--icon", str(icon)))
    args.append(str(PROJECT / "gui.py"))
    print("Проверен локальный FFmpeg:", version, flush=True)
    subprocess.run(args, cwd=PROJECT, check=True)
    output = PROJECT / "dist" / "FFClass"
    for binary in ("ffmpeg.exe", "ffprobe.exe"):
        if not (output / "_internal" / "bin" / binary).is_file():
            raise RuntimeError(f"Сборка не содержит _internal/bin/{binary}.")
    if not (output / "FFClass.exe").is_file():
        raise RuntimeError("После сборки не найден FFClass.exe.")
    for name in RELEASE_FILES:
        shutil.copy2(PROJECT / name, output / name)
    print("Готова папка приложения:", output)
    if make_zip:
        download_zip = shutil.make_archive(str(PROJECT / "dist" / "FFClass-Windows"), "zip",
                                           root_dir=PROJECT / "dist", base_dir="FFClass")
        with ZipFile(download_zip) as archive:
            names = set(archive.namelist())
            required = {f"FFClass/{name}" for name in (*RELEASE_FILES, "FFClass.exe")}
            required.update(f"FFClass/_internal/bin/{name}" for name in ("ffmpeg.exe", "ffprobe.exe"))
            missing = required - names
            if missing:
                raise RuntimeError("В ZIP отсутствуют файлы: " + ", ".join(sorted(missing)))
        print("Готов ZIP для GitHub Release → Assets:", download_zip)
    print("Передавайте пользователю ВСЮ папку FFClass. Никакого Python/venv/FFmpeg на его ПК не требуется.")


if __name__ == "__main__":
    try:
        build()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, KeyError) as error:
        sys.exit(f"Ошибка сборки FFClass: {error}")
