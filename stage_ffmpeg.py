"""Stage a verified local FFmpeg pair for the FFClass distribution.

Run on the build machine, for example:
    python stage_ffmpeg.py --source C:\\tools\\ffmpeg\\bin

Ship the resulting bin directory beside the EXE, or bundle bin/ffmpeg.exe and
bin/ffprobe.exe into bin with the freezer. End users do not run this script.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def check(program, args):
    result = subprocess.run(
        [str(program), *args], input=b"", stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=12,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace")[-450:].strip()
        raise RuntimeError(f"{program.name} не прошёл проверку: {message or result.returncode}")
    return result.stdout.decode("utf-8", "replace")


def source_pair(folder):
    suffix = ".exe" if sys.platform == "win32" else ""
    if folder is None:
        found = shutil.which("ffmpeg" + suffix)
        if not found:
            raise FileNotFoundError("Укажите --source с папкой ffmpeg и ffprobe")
        folder = Path(found).resolve().parent
    else:
        folder = Path(folder).expanduser().resolve()
        if folder.is_file():
            folder = folder.parent
    files = [folder / ("ffmpeg" + suffix), folder / ("ffprobe" + suffix)]
    if not all(file.is_file() for file in files):
        raise FileNotFoundError("В одной папке нужны ffmpeg и ffprobe для этой системы")
    return files


def verify_pair(ffmpeg, ffprobe):
    version = check(ffmpeg, ["-version"]).splitlines()[0]
    check(ffprobe, ["-version"])
    # A tiny real encode detects old builds where the native AAC encoder is experimental.
    check(ffmpeg, ["-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                   "-t", "0.1", "-c:a", "aac", "-f", "null", "-"])
    return version


def stage(source, destination):
    ffmpeg, ffprobe = source_pair(source)
    version = verify_pair(ffmpeg, ffprobe)
    destination = Path(destination).expanduser().resolve()
    if ffmpeg.parent == destination:
        raise ValueError("Папка назначения совпадает с исходной")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ffclass_media_", dir=destination.parent) as temporary:
        staged = Path(temporary) / "bin"
        staged.mkdir()
        for original in (ffmpeg, ffprobe):
            shutil.copy2(original, staged / original.name)
        verify_pair(staged / ffmpeg.name, staged / ffprobe.name)
        manifest = {
            "version": version,
            "files": {name: hashlib.sha256((staged / name).read_bytes()).hexdigest()
                      for name in (ffmpeg.name, ffprobe.name)},
        }
        (staged / "ffclass_ffmpeg.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        backup = Path(temporary) / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            try:
                staged.rename(destination)
            except PermissionError:
                # Some Windows security tools block directory moves while allowing
                # normal file copies. Keep the verified staging copy until complete.
                shutil.copytree(staged, destination)
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            if backup.exists():
                backup.rename(destination)
            raise
    return version, destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверить и собрать локальную пару FFmpeg для FFClass")
    parser.add_argument("--source", help="Папка с ffmpeg и ffprobe; по умолчанию используется PATH")
    parser.add_argument("--dest", default=str(Path(__file__).resolve().parent / "bin"))
    args = parser.parse_args()
    try:
        version, path = stage(args.source, args.dest)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Ошибка подготовки FFmpeg: {exc}\n")
    print(f"Готово: {version}\nФайлы: {path}")
    if sys.platform != "win32":
        print("Для Linux проверьте также системные библиотеки: бинарники могут быть динамически связаны.")
