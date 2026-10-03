"""Local FFmpeg/ffprobe execution and media encoding for FFClass.

No GUI widgets live here. QProcess emits progress back to gui.py via signals.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal, Slot


def extract_encoder(value):
    text = str(value or "").strip()
    match = re.search(r"(?:Энкодер|Encoder)\s*:\s*([\w-]+)", text, re.I)
    return match.group(1) if match else (text or "libx264")


class MediaEngine(QObject):
    videoSelected = Signal(str)
    processingProgress = Signal(str)
    processingFinished = Signal(str)
    processingError = Signal(str)

    def __init__(self, config_data, metrics_timer=None, parent=None):
        super().__init__(parent)
        self.config_data = config_data
        self._metrics_timer = metrics_timer
        self.selected_video_path = None
        self.selected_video_info = None
        self.ffmpeg_process = None
        self.output_path = None
        self._progress_buffer = ""
        self._encoding_started_at = 0.0
        self._cancel_requested = False

    def _message(self, ru, en):
        return en if self.config_data.get("language") == "EN" else ru

    @staticmethod
    def collect_metrics():
        return MediaEngine._collect_metrics()

    @classmethod
    def ffmpeg_status(cls):
        binary = cls._find_media_binary("ffmpeg")
        status = {"available": False, "version": "", "path": binary or ""}
        if binary:
            try:
                result = subprocess.run(
                    [binary, "-version"], capture_output=True, text=True, timeout=4,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                first_line = result.stdout.splitlines()[0] if result.stdout else ""
                match = re.search(r"ffmpeg version\s+([^\s]+)", first_line, re.I)
                status["available"] = result.returncode == 0
                status["version"] = match.group(1) if match else ("installed" if status["available"] else "")
            except (OSError, subprocess.SubprocessError):
                pass
        return status

    @classmethod
    def media_readiness(cls):
        """Check the actual pair and AAC before a job; safe to run in a worker thread."""
        ffmpeg = cls._find_media_binary("ffmpeg")
        ffprobe = cls._find_media_binary("ffprobe")
        if not ffmpeg or not ffprobe:
            return {"ready": False, "reason": "missing", "ffmpeg": ffmpeg or "", "ffprobe": ffprobe or ""}
        if Path(ffmpeg).resolve().parent != Path(ffprobe).resolve().parent:
            return {"ready": False, "reason": "unpaired", "ffmpeg": ffmpeg, "ffprobe": ffprobe}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            version = subprocess.run([ffmpeg, "-version"], stdin=subprocess.DEVNULL,
                                     capture_output=True, timeout=5, creationflags=flags)
            probe = subprocess.run([ffprobe, "-version"], stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=5, creationflags=flags)
            if version.returncode or probe.returncode:
                return {"ready": False, "reason": "broken", "ffmpeg": ffmpeg, "ffprobe": ffprobe}
            smoke = subprocess.run(
                [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                 "-t", "0.1", "-c:a", "aac", "-f", "null", "-"],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=10, creationflags=flags)
            if smoke.returncode:
                return {"ready": False, "reason": "aac", "ffmpeg": ffmpeg, "ffprobe": ffprobe}
            version_lines = version.stdout.decode("utf-8", "replace").splitlines()
            return {"ready": True, "reason": "ready", "ffmpeg": ffmpeg, "ffprobe": ffprobe,
                    "version": version_lines[0] if version_lines else ""}
        except (OSError, subprocess.SubprocessError):
            return {"ready": False, "reason": "broken", "ffmpeg": ffmpeg, "ffprobe": ffprobe}

    @staticmethod
    def _find_media_binary(name):
        executable = f"{name}.exe" if sys.platform == "win32" else name
        root = Path(__file__).resolve().parent
        # The packaged pair wins over any ancient FFmpeg on the user's PATH.
        locations = []
        if getattr(sys, "frozen", False):
            locations.extend((Path(sys.executable).resolve().parent,
                              Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))))
        locations.append(root)
        candidates = []
        for location in locations:
            candidates.extend((location / "bin" / executable,
                               location / "ffmpeg" / "bin" / executable,
                               location / executable))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        if getattr(sys, "frozen", False):
            return None  # Installed FFClass must never depend on the system PATH.
        return shutil.which(executable) or shutil.which(name)


    @staticmethod
    def _format_bytes(value):
        size = float(value or 0)
        if size < 1024 ** 2:
            return f"{size / 1024:.1f} KB"
        if size < 1024 ** 3:
            return f"{size / 1024 ** 2:.1f} MB"
        return f"{size / 1024 ** 3:.2f} GB"


    @staticmethod
    def _format_duration(seconds):
        total = max(0, int(round(float(seconds or 0))))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


    @Slot(str)
    def selectVideoPath(self, filename):
        path = Path(filename).expanduser().resolve()
        if not path.is_file():
            self.processingError.emit(self._message("Файл не найден", "File not found"))
            return
        allowed = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
        if path.suffix.lower() not in allowed:
            self.processingError.emit(
                self._message("Неподдерживаемый формат видео", "Unsupported video format")
            )
            return

        # No child process starts here: filename, extension and size are enough
        # to offer a task. Probe detailed media metadata after Start is clicked.
        self.selected_video_path = path
        self.selected_video_info = None
        info = {
            "name": path.name, "path": str(path), "size": path.stat().st_size,
            "size_label": self._format_bytes(path.stat().st_size),
            "resolution": "—", "duration_label": "—", "duration": 0,
        }
        self.videoSelected.emit(json.dumps(info, ensure_ascii=False))


    def _probe_video(self, path):
        ffprobe = self._find_media_binary("ffprobe")
        if not ffprobe:
            raise RuntimeError(
                self._message(
                    "ffprobe не найден. При сборке добавьте ffmpeg и ffprobe в папку bin рядом с FFClass.",
                    "ffprobe was not found. Bundle ffmpeg and ffprobe in the bin folder beside FFClass.",
                )
            )
        command = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,bit_rate",
            "-of", "json",
            str(path),
        ]
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(
                self._message("Не удалось прочитать видео: ", "Could not inspect the video: ")
                + result.stderr[-300:].strip()
            )
        payload = json.loads(result.stdout or "{}")
        video = next(
            (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
            None,
        )
        if not video:
            raise RuntimeError(self._message("В файле нет видеопотока", "The file has no video stream"))
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        try:
            fps = round(float(Fraction(rate)), 2)
        except (ValueError, ZeroDivisionError):
            fps = 0
        file_format = payload.get("format", {})
        duration = float(file_format.get("duration") or 0)
        size = int(file_format.get("size") or path.stat().st_size)
        bitrate = int(video.get("bit_rate") or file_format.get("bit_rate") or 0)
        # Called after Start. No FFmpeg preview process is created.
        thumbnail = ""
        return {
            "name": path.name,
            "path": str(path),
            "codec": str(video.get("codec_name") or "—").upper(),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "resolution": f"{video.get('width', 0)}×{video.get('height', 0)}",
            "fps": fps,
            "bitrate": bitrate,
            "bitrate_label": f"{bitrate / 1_000_000:.2f} Mbps" if bitrate else "—",
            "size": size,
            "size_label": self._format_bytes(size),
            "duration": duration,
            "duration_label": self._format_duration(duration),
            "thumbnail": thumbnail,
        }


    @Slot()
    def clearSelectedVideo(self):
        if self.ffmpeg_process and self.ffmpeg_process.state() != QProcess.ProcessState.NotRunning:
            return
        self.selected_video_path = None
        self.selected_video_info = None


    def _recommended_encoder(self):
        hardware = self.config_data.get("hardware", {})
        encoder = extract_encoder(
            hardware.get("rec") or hardware.get("ffmpeg_encoder") or "libx264"
        ).lower()
        allowed = {
            "h264_nvenc", "hevc_nvenc", "av1_nvenc",
            "h264_qsv", "hevc_qsv", "av1_qsv",
            "h264_amf", "hevc_amf", "av1_amf",
            "libx264", "libx265", "libsvtav1", "libaom-av1",
        }
        gpu = str(hardware.get("gpu") or "").strip().lower()
        if encoder.endswith(("_qsv", "_nvenc", "_amf")) and gpu in {"", "—", "none", "n/a", "unknown", "не определена"}:
            return "libx264"
        return encoder if encoder in allowed else "libx264"


    @staticmethod
    def _unique_output_path(source, extension="mp4"):
        candidate = source.with_name(f"{source.stem}_ffclass.{extension}")
        index = 2
        while candidate.exists():
            candidate = source.with_name(f"{source.stem}_ffclass_{index}.{extension}")
            index += 1
        return candidate


    def _encoder_arguments(self, encoder, preset, target_size_mb, duration, options=None):
        options = options or {}
        speed = preset if preset in {"fast", "balanced", "quality"} else "balanced"
        args = ["-c:v", encoder]
        if target_size_mb and duration > 0:
            audio_kbps = int(options.get("audio_bitrate") or 96)
            total_kbps = int(float(target_size_mb) * 8 * 1024 * .92 / duration)
            video_kbps = max(80, total_kbps - audio_kbps)
            args += ["-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps}k", "-bufsize", f"{video_kbps * 2}k"]
        elif options.get("rate_mode") == "cbr":
            video_kbps = int(options.get("bitrate_kbps", 2500))
            args += ["-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps}k", "-bufsize", f"{video_kbps * 2}k"]
        elif encoder in {"libx264", "libx265"}:
            presets = {"fast": "veryfast", "balanced": "medium", "quality": "slow"}
            quality = {"fast": "27", "balanced": "23", "quality": "18"}
            if options.get("rate_mode") == "crf":
                quality[speed] = str(options.get("crf", 23))
            args += ["-preset", presets[speed], "-crf", quality[speed]]
        elif encoder.endswith("_nvenc"):
            presets = {"fast": "p2", "balanced": "p4", "quality": "p6"}
            quality = {"fast": "29", "balanced": "23", "quality": "18"}
            args += ["-preset", presets[speed], "-cq", quality[speed], "-b:v", "0"]
        elif encoder.endswith("_qsv"):
            presets = {"fast": "veryfast", "balanced": "medium", "quality": "veryslow"}
            quality = {"fast": "29", "balanced": "23", "quality": "18"}
            args += ["-preset", presets[speed], "-global_quality", quality[speed]]
        elif encoder.endswith("_amf"):
            presets = {"fast": "speed", "balanced": "balanced", "quality": "quality"}
            quality = {"fast": "29", "balanced": "23", "quality": "18"}
            args += ["-quality", presets[speed], "-qp_i", quality[speed], "-qp_p", quality[speed]]
        else:
            if encoder == "libsvtav1":
                args += ["-preset", {"fast":"10","balanced":"6","quality":"4"}[speed], "-crf", str(options.get("crf", 30))]
            elif encoder == "mpeg4":
                args += ["-q:v", "3" if speed == "quality" else "5" if speed == "balanced" else "8"]
            else:
                args += ["-crf", str(options.get("crf", 28 if speed == "fast" else 23 if speed == "balanced" else 18))]
        return args

    @staticmethod
    def _catalog_filters(options):
        filters = []
        crop = options.get("crop_aspect", "none")
        if crop == "1:1": filters.append("crop=w='trunc(min(iw,ih)/2)*2':h='trunc(min(ih,iw)/2)*2'")
        elif crop == "16:9": filters.append("crop=w='trunc(min(iw,ih*16/9)/2)*2':h='trunc(min(ih,iw*9/16)/2)*2'")
        elif crop == "9:16": filters.append("crop=w='trunc(min(iw,ih*9/16)/2)*2':h='trunc(min(ih,iw*16/9)/2)*2'")
        resolution = str(options.get("resolution") or "original")
        if resolution in {"1080", "720", "480"}:
            filters.append(f"scale=w='trunc(iw*min(1,{resolution}/max(iw,ih))/2)*2':h='trunc(ih*min(1,{resolution}/max(iw,ih))/2)*2'")
        rotation = options.get("rotate", "none")
        if rotation == "90": filters.append("transpose=clock")
        elif rotation == "180": filters.extend(["hflip", "vflip"])
        elif rotation == "270": filters.append("transpose=cclock")
        if options.get("flip") == "horizontal": filters.append("hflip")
        elif options.get("flip") == "vertical": filters.append("vflip")
        if options.get("denoise") == "light": filters.append("hqdn3d=2:2:3:3")
        elif options.get("denoise") == "strong": filters.append("hqdn3d=4:4:6:6")
        if options.get("sharpen"): filters.append("unsharp=5:5:0.7:5:5:0")
        if options.get("grayscale"): filters.append("hue=s=0")
        return filters


    @Slot(str)
    def startEncoding(self, options_json):
        if not self.selected_video_path or not self.selected_video_info:
            self.processingError.emit(self._message("Сначала выберите видео", "Choose a video first"))
            return
        if self.ffmpeg_process and self.ffmpeg_process.state() != QProcess.ProcessState.NotRunning:
            return
        try:
            options = json.loads(options_json or "{}")
            if not isinstance(options, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            options = {}
        goal = options.get("goal", "archive")
        if goal not in {"send", "archive", "audio", "repair_audio", "editing", "remux"}:
            self.processingError.emit(self._message("Неверная цель кодирования", "Invalid encoding goal"))
            return
        special = {
            "repair_audio": {"audio_action": {"fix", "convert", "remove"}, "audio_format": {"pcm", "mp3", "aac", "flac"}, "audio_channels": {"source", "stereo", "mono"}},
            "editing": {"editing_app": {"davinci_linux", "davinci_windows", "premiere", "finalcut"}, "editing_goal": {"proxy", "cfr", "pcm"}},
            "remux": {"container": {"mp4", "mkv", "mov"}},
        }
        if goal in special:
            for key, permitted in special[goal].items():
                if options.get(key) not in permitted:
                    self.processingError.emit(self._message("Выберите параметры задачи", "Choose the task settings"))
                    return
        if goal == "audio" and options.get("audio_format") not in {"mp3", "aac", "flac", "pcm"}:
            self.processingError.emit(self._message("Выберите формат звука", "Choose an audio format"))
            return
        choices = {
            "preset": {"fast", "balanced", "quality"},
            "resolution": {"original", "1080", "720", "480"},
            "video_codec": {"auto", "libx264", "libx265", "libsvtav1", "mpeg4"},
            "rate_mode": {"auto", "crf", "cbr"},
            "fps": {"original", "24", "25", "30", "50", "60"},
            "rotate": {"none", "90", "180", "270"},
            "flip": {"none", "horizontal", "vertical"},
            "denoise": {"none", "light", "strong"},
            "audio_bitrate": {64, 96, 128, 192, 256, 320},
            "audio_channels": {"source", "mono", "stereo"},
            "gop": {0, 30, 60, 120, 240},
            "crop_aspect": {"none", "1:1", "16:9", "9:16"},
            "sample_rate": {0, 22050, 44100, 48000, 96000},
            "highpass": {0, 80, 120, 200},
            "lowpass": {0, 8000, 12000},
        }
        if any(key in options and (type(options[key]) is bool or options[key] not in values) for key, values in choices.items()):
            self.processingError.emit(self._message("Неверные параметры кодирования", "Invalid encoding settings"))
            return
        if any(key in options and type(options[key]) is not bool for key in ("normalize", "mute", "sharpen", "grayscale", "strip_metadata", "faststart")):
            self.processingError.emit(self._message("Неверные параметры кодирования", "Invalid encoding settings"))
            return
        if any(type(options.get(key)) is not int or not low <= options[key] <= high for key, low, high in (("crf", 0, 51), ("bitrate_kbps", 100, 100000)) if key in options):
            self.processingError.emit(self._message("Неверное значение качества или битрейта", "Invalid quality or bitrate"))
            return
        if goal == "audio" and options.get("mute"):
            self.processingError.emit(self._message("Нельзя извлечь звук и одновременно удалить его", "Audio extraction cannot remove audio"))
            return
        if goal == "send" and options.get("target_size_mb") not in (25, 100):
            self.processingError.emit(self._message("Выберите 25 или 100 МБ", "Choose 25 or 100 MB"))
            return
        duration = float(self.selected_video_info.get("duration") or 0)
        if goal in {"send", "archive"}:
            try:
                start = float(options.get("trim_start") or 0)
                end = float(options.get("trim_end") or duration)
            except (TypeError, ValueError):
                start, end = -1, -1
            if not (0 <= start < end <= duration):
                self.processingError.emit(self._message("Неверный интервал обрезки", "Invalid trim interval"))
                return
            if goal == "send" and (int(options["target_size_mb"] * 8 * 1024 * .92 / (end - start)) - int(options.get("audio_bitrate") or 96)) < 80:
                self.processingError.emit(self._message("Длительность слишком велика для этого лимита", "Duration is too long for this size limit"))
                return
        if goal == "audio":
            extension = {"aac": "m4a", "pcm": "wav"}.get(options["audio_format"], options["audio_format"])
        elif goal == "repair_audio":
            extension = "mkv" if options["audio_format"] == "flac" and options["audio_action"] != "remove" else "mov" if options["audio_format"] == "pcm" and options["audio_action"] != "remove" else "mkv" if options["audio_action"] == "remove" else "mp4"
        elif goal == "editing":
            extension = "mov" if options["editing_goal"] in {"proxy", "pcm"} else "mp4"
        else:
            extension = options.get("container", "mp4")
        if extension not in {"mp3", "m4a", "flac", "wav", "mp4", "mkv", "mov"}:
            self.processingError.emit(self._message("Неподдерживаемый формат", "Unsupported output format"))
            return
        self._cancel_requested = False
        self.output_path = self._unique_output_path(self.selected_video_path, extension)
        chosen_codec = options.get("video_codec", "auto")
        encoder = self._recommended_encoder() if chosen_codec == "auto" else chosen_codec
        if goal == "audio":
            encoder = {"mp3": "libmp3lame", "aac": "aac", "flac": "flac", "pcm": "pcm_s16le"}[options["audio_format"]]
        if goal in {"repair_audio", "remux"} or (goal == "editing" and options["editing_goal"] == "pcm"):
            encoder = "copy"
        if goal == "editing" and options["editing_goal"] in {"proxy", "cfr"}:
            encoder = "dnxhd" if options["editing_goal"] == "proxy" and options["editing_app"].startswith("davinci") else "prores_ks" if options["editing_goal"] == "proxy" else "libx264"
        if chosen_codec == "auto" and options.get("rate_mode") == "crf":
            encoder = "libx264"
        self._launch_encoding(options, encoder, allow_fallback=goal in {"send", "archive"} and chosen_codec == "auto" and encoder != "libx264")


    def _launch_encoding(self, options, encoder, allow_fallback):
        ffmpeg = self._find_media_binary("ffmpeg")
        if not ffmpeg:
            self.processingError.emit(
                self._message(
                    "FFmpeg не найден. При сборке добавьте ffmpeg и ffprobe в папку bin рядом с FFClass.",
                    "FFmpeg was not found. Bundle ffmpeg and ffprobe in the bin folder beside FFClass.",
                )
            )
            return
        duration = float(self.selected_video_info.get("duration") or 0)
        goal = options.get("goal", "archive")
        start = float(options.get("trim_start") or 0) if goal != "audio" else 0
        end = float(options.get("trim_end") or duration) if goal != "audio" else duration
        effective_duration = end - start
        preset = str(options.get("preset") or "balanced")
        target = options.get("target_size_mb") if goal == "send" else None
        args = ["-y", "-nostdin", "-loglevel", "error", "-i", str(self.selected_video_path)]
        audio_rate = int(options.get("audio_bitrate") or (96 if target else 192))
        if goal in {"repair_audio", "editing", "remux"}:
            if goal == "remux":
                args += ["-map", "0", "-c", "copy"]
            elif goal == "repair_audio":
                action = options["audio_action"]
                input_codec = str(self.selected_video_info.get("codec") or "").lower()
                copy_video = self.output_path.suffix == ".mkv" or input_codec in {"h264", "hevc", "mpeg4", "prores", "dnxhd"}
                args += ["-map", "0:v:0", "-c:v", "copy" if copy_video else "libx264"]
                if not copy_video: args += ["-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p"]
                if action == "remove":
                    args += ["-an"]
                else:
                    audio_codec = {"pcm": "pcm_s16le", "mp3": "libmp3lame", "aac": "aac", "flac": "flac"}[options["audio_format"]]
                    args += ["-map", "0:a:0", "-c:a", audio_codec]
                    if options["audio_format"] in {"mp3", "aac"}: args += ["-b:a", "192k"]
                    if options["audio_channels"] in {"mono", "stereo"}: args += ["-ac", "1" if options["audio_channels"] == "mono" else "2"]
            else:
                edit = options["editing_goal"]
                if edit == "pcm" and str(self.selected_video_info.get("codec") or "").lower() not in {"h264", "hevc", "mpeg4", "prores", "dnxhd"}:
                    encoder = "libx264"
                args += ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", encoder]
                if edit == "proxy":
                    # Editing codecs require appropriate pixel formats and frame sizes.
                    args += ["-vf", "scale=w='trunc(iw*min(1,1280/iw)/2)*2':h='trunc(ih*min(1,1280/iw)/2)*2',format=yuv422p10le"] if encoder == "prores_ks" else ["-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv422p", "-b:v", "90M"]
                    args += ["-c:a", "pcm_s16le"]
                elif edit == "cfr":
                    fps = float(self.selected_video_info.get("fps") or 30)
                    fps = min(120, max(1, round(fps)))
                    args += ["-vsync", "cfr", "-r", str(fps), "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"]
                else:
                    if encoder == "libx264": args += ["-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p"]
                    args += ["-c:a", "pcm_s16le"]
            args += ["-progress", "pipe:1", "-nostats", str(self.output_path)]
            self._start_ffmpeg_process(ffmpeg, args, options, encoder, allow_fallback, effective_duration)
            return
        if goal == "audio":
            codec = {"mp3": "libmp3lame", "aac": "aac", "flac": "flac", "pcm": "pcm_s16le"}[options["audio_format"]]
            args += ["-map", "0:a:0", "-vn", "-c:a", codec]
            if codec in {"libmp3lame", "aac"}: args += ["-b:a", f"{audio_rate}k"]
        else:
            if start:
                args += ["-ss", str(start)]
            if end < duration:
                args += ["-t", str(effective_duration)]
            args += ["-map", "0:v:0"]
            if self.output_path.suffix == ".mkv":
                args += ["-map", "0:a?", "-map", "0:s?", "-c:s", "copy"]
            elif not options.get("mute"):
                args += ["-map", "0:a:0?"]
            args += self._encoder_arguments(encoder, preset, target, effective_duration, options)
            if options.get("gop"): args += ["-g", str(options["gop"])]
            filters = self._catalog_filters(options)
            if filters: args += ["-vf", ",".join(filters)]
            if options.get("fps", "original") != "original": args += ["-r", str(options["fps"])]
            if options.get("mute"): args += ["-an"]
            else:
                args += ["-c:a", "aac", "-b:a", f"{audio_rate}k"]
                if options.get("audio_channels") in {"mono", "stereo"}: args += ["-ac", "1" if options["audio_channels"] == "mono" else "2"]
            if self.output_path.suffix == ".mp4" and options.get("faststart", True):
                args += ["-movflags", "+faststart"]
        if goal == "audio":
            if options.get("audio_channels") in {"mono", "stereo"}: args += ["-ac", "1" if options["audio_channels"] == "mono" else "2"]
        if not options.get("mute"):
            if options.get("sample_rate"): args += ["-ar", str(options["sample_rate"])]
            audio_filters = []
            if options.get("highpass"): audio_filters.append(f"highpass=f={options['highpass']}")
            if options.get("lowpass"): audio_filters.append(f"lowpass=f={options['lowpass']}")
            if options.get("normalize"): audio_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
            if audio_filters: args += ["-af", ",".join(audio_filters)]
        if options.get("strip_metadata"): args += ["-map_metadata", "-1"]
        args += ["-progress", "pipe:1", "-nostats", str(self.output_path)]
        self._start_ffmpeg_process(ffmpeg, args, options, encoder, allow_fallback, effective_duration)

    def _start_ffmpeg_process(self, ffmpeg, args, options, encoder, allow_fallback, effective_duration):
        self._active_options = options
        self._active_encoder = encoder
        self._allow_fallback = allow_fallback
        self._progress_values = {}
        self._progress_buffer = ""
        self._encoding_started_at = time.monotonic()
        self._encoding_duration = effective_duration
        process = QProcess(self)
        process.setProgram(ffmpeg)
        process.setArguments(args)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardOutput.connect(self._read_ffmpeg_progress)
        process.finished.connect(self._encoding_finished)
        process.errorOccurred.connect(self._encoding_process_error)
        self.ffmpeg_process = process
        if self._metrics_timer:
            self._metrics_timer.start()
        process.start()


    def _read_ffmpeg_progress(self):
        if not self.ffmpeg_process:
            return
        chunk = bytes(self.ffmpeg_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._progress_buffer += chunk
        while "\n" in self._progress_buffer:
            line, self._progress_buffer = self._progress_buffer.split("\n", 1)
            if "=" not in line:
                continue
            key, value = line.strip().split("=", 1)
            self._progress_values[key] = value
            if key == "progress":
                self._emit_progress()


    def _emit_progress(self):
        duration = float(getattr(self, "_encoding_duration", 0) or 0)
        raw_time = self._progress_values.get("out_time_us") or self._progress_values.get("out_time_ms") or "0"
        try:
            encoded_seconds = float(raw_time) / 1_000_000
        except ValueError:
            encoded_seconds = 0
        percent = min(99.9, encoded_seconds / duration * 100) if duration else 0
        if self._progress_values.get("progress") == "end":
            percent = 100
        elapsed = max(0.001, time.monotonic() - self._encoding_started_at)
        eta_seconds = (elapsed * (100 - percent) / percent) if percent > 0 else 0
        payload = {
            "percent": round(percent, 1),
            "eta": self._format_duration(eta_seconds) if percent > 0 else "—",
            "speed": self._progress_values.get("speed", "—"),
            "status": self._message("FFmpeg кодирует видео", "FFmpeg is encoding the video"),
            "output_path": str(self.output_path or ""),
            "encoder": self._active_encoder,
        }
        self.processingProgress.emit(json.dumps(payload, ensure_ascii=False))


    def _encoding_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            if self._metrics_timer:
                self._metrics_timer.stop()
            if self.output_path:
                self.output_path.unlink(missing_ok=True)
            process = self.ffmpeg_process
            self.ffmpeg_process = None
            if process:
                process.deleteLater()
            self.processingError.emit(self._message("Не удалось запустить FFmpeg", "Could not start FFmpeg"))


    def _encoding_finished(self, exit_code, _exit_status):
        if self._metrics_timer:
            self._metrics_timer.stop()
        process = self.ffmpeg_process
        if process is None:
            return
        stderr = bytes(process.readAllStandardError()).decode("utf-8", errors="replace") if process else ""
        self.ffmpeg_process = None
        if process:
            process.deleteLater()
        cancelled = self._cancel_requested
        if cancelled:
            if self.output_path:
                self.output_path.unlink(missing_ok=True)
            self.processingFinished.emit(json.dumps({"cancelled": True}))
        elif exit_code != 0 and self._allow_fallback and self._active_encoder != "libx264":
            if self.output_path:
                self.output_path.unlink(missing_ok=True)
            self.processingProgress.emit(json.dumps({
                "percent": 0,
                "eta": "—",
                "speed": "—",
                "status": self._message("Аппаратный энкодер недоступен — переход на libx264", "Hardware encoder unavailable — switching to libx264"),
                "output_path": str(self.output_path or ""),
                "encoder": "libx264",
            }, ensure_ascii=False))
            self._launch_encoding(self._active_options, "libx264", allow_fallback=False)
            return
        elif exit_code != 0:
            if self.output_path:
                self.output_path.unlink(missing_ok=True)
            if "encoder 'aac' is experimental" in stderr.lower() or "experimental codecs are not enabled" in stderr.lower():
                self.processingError.emit(self._message(
                    "Используется устаревший FFmpeg с экспериментальным AAC. Установите проверенные ffmpeg.exe и ffprobe.exe в папку bin рядом с приложением.",
                    "This FFmpeg build has experimental AAC. Place a verified ffmpeg and ffprobe pair in the bin folder next to the app."
                ))
            else:
                self.processingError.emit(
                    self._message("Ошибка FFmpeg: ", "FFmpeg error: ") + (stderr[-500:].strip() or str(exit_code))
                )
        else:
            size = self.output_path.stat().st_size if self.output_path and self.output_path.exists() else 0
            result = {
                "cancelled": False,
                "output_path": str(self.output_path or ""),
                "output_name": self.output_path.name if self.output_path else "output.mp4",
                "output_size": size,
                "encoder": self._active_encoder,
            }
            self.processingFinished.emit(json.dumps(result, ensure_ascii=False))


    @Slot()
    def cancelEncoding(self):
        process = self.ffmpeg_process
        if not process or process.state() == QProcess.ProcessState.NotRunning:
            return
        self._cancel_requested = True
        process.terminate()
        QTimer.singleShot(2000, process, lambda: process.kill() if process.state() != QProcess.ProcessState.NotRunning else None)


    @staticmethod
    def _collect_metrics():
        metrics = {
            "cpu_percent": None,
            "gpu_percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
        }
        try:
            import psutil

            memory = psutil.virtual_memory()
            metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
            metrics["memory_used_gb"] = round(memory.used / 1024 ** 3, 2)
            metrics["memory_total_gb"] = round(memory.total / 1024 ** 3, 2)
        except (ImportError, OSError):
            if sys.platform == "win32":
                try:
                    import ctypes

                    class MemoryStatus(ctypes.Structure):
                        _fields_ = [
                            ("length", ctypes.c_ulong),
                            ("memory_load", ctypes.c_ulong),
                            ("total_phys", ctypes.c_ulonglong),
                            ("avail_phys", ctypes.c_ulonglong),
                            ("total_page_file", ctypes.c_ulonglong),
                            ("avail_page_file", ctypes.c_ulonglong),
                            ("total_virtual", ctypes.c_ulonglong),
                            ("avail_virtual", ctypes.c_ulonglong),
                            ("avail_extended_virtual", ctypes.c_ulonglong),
                        ]

                    status = MemoryStatus()
                    status.length = ctypes.sizeof(MemoryStatus)
                    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                        metrics["memory_total_gb"] = round(status.total_phys / 1024 ** 3, 2)
                        metrics["memory_used_gb"] = round((status.total_phys - status.avail_phys) / 1024 ** 3, 2)
                except (AttributeError, OSError):
                    pass

        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi:
            try:
                result = subprocess.run(
                    [nvidia_smi, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                values = [float(item.strip()) for item in result.stdout.splitlines() if item.strip()]
                if values:
                    metrics["gpu_percent"] = max(values)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        if metrics["gpu_percent"] is None and sys.platform == "win32":
            powershell = shutil.which("powershell.exe") or shutil.which("powershell")
            if powershell:
                try:
                    command = "((Get-Counter '\\GPU Engine(*)\\Utilization Percentage').CounterSamples | Measure-Object CookedValue -Sum).Sum"
                    result = subprocess.run(
                        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    metrics["gpu_percent"] = min(100.0, max(0.0, float(result.stdout.strip())))
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
        return metrics
