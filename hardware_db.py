"""FFClass: hardware catalogue and conservative FFmpeg encoder selection.

Drop this file alongside oscheck.py and custom_input.py. No GUI, no PC scanning,
no conversion of user files. Pass names obtained from your existing scanner.

The catalogue is a *candidate* database, not a guarantee of video encoder support.
FFmpeg runtime probing checks both compiled encoder presence and a real one-frame
encode. It cannot guarantee that every future resolution, driver or input will work.

References (informational; hardware capability varies by exact SKU):
  https://developer.nvidia.com/video-codec-sdk
  https://developer.nvidia.com/ffmpeg
  https://www.intel.com/content/www/us/en/docs/onevpl/developer-reference-media-intel-hardware/1-1/overview.html
  https://github.com/GPUOpen-LibrariesAndSDKs/AMF/wiki/FFmpeg-and-AMF-HW-Acceleration

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import re
import shutil
import subprocess
from typing import Iterable, Literal, Sequence

Codec = Literal["h264", "hevc", "av1"]

# Named aliases are normalized to FFmpeg's codec family names.
CODEC_ALIASES = {
    "h264": "h264", "avc": "h264", "x264": "h264",
    "h265": "hevc", "h.265": "hevc", "hevc": "hevc", "x265": "hevc",
    "av1": "av1",
}
SOFTWARE_ENCODERS = {
    "h264": ("libx264",),
    "hevc": ("libx265",),
    "av1": ("libsvtav1", "libaom-av1"),
}
ENCODERS = {
    "nvidia": {"h264": "h264_nvenc", "hevc": "hevc_nvenc", "av1": "av1_nvenc"},
    "amd": {"h264": "h264_amf", "hevc": "hevc_amf", "av1": "av1_amf"},
    "intel": {"h264": "h264_qsv", "hevc": "hevc_qsv", "av1": "av1_qsv"},
}


@dataclass(frozen=True)
class GPUFamily:
    """One hardware family with *possible* encoders, subject to runtime verification."""
    family: str
    vendor: str
    pattern: str
    possible_codecs: tuple[str, ...]
    priority: int = 50  # higher means try first when multiple GPUs exist
    note: str = ""


# More specific rules must precede generic vendor rules. Do not infer encoder
# support solely from a GPU manufacturer or an RTX-like substring.
GPU_CATALOG: tuple[GPUFamily, ...] = (
    # NVIDIA. 40/50-class GeForce support AV1 encode; RTX 20/30 do not.
    GPUFamily("GeForce RTX 50", "nvidia", r"\b(?:geforce\s+)?rtx\s*50[5-9]0\b", ("h264", "hevc", "av1"), 100),
    GPUFamily("GeForce RTX 40", "nvidia", r"\b(?:geforce\s+)?rtx\s*40[5-9]0\b", ("h264", "hevc", "av1"), 95),
    GPUFamily("GeForce RTX 30", "nvidia", r"\b(?:geforce\s+)?rtx\s*30[5-9]0\b", ("h264", "hevc"), 90),
    GPUFamily("GeForce RTX 20", "nvidia", r"\b(?:geforce\s+)?rtx\s*20[5-9]0\b", ("h264", "hevc"), 85),
    GPUFamily("GeForce GTX 16", "nvidia", r"\b(?:geforce\s+)?gtx\s*16\d{2}\b", ("h264", "hevc"), 80),
    GPUFamily("GeForce GTX 10", "nvidia", r"\b(?:geforce\s+)?gtx\s*10\d{2}\b", ("h264", "hevc"), 70),
    GPUFamily("GeForce GTX 9", "nvidia", r"\b(?:geforce\s+)?gtx\s*9\d{2}\b", ("h264", "hevc"), 60),
    GPUFamily("GeForce GTX 750", "nvidia", r"\bgtx\s*750(?:\s*ti)?\b", ("h264",), 45, "Older models: H.264 candidate only."),
    GPUFamily("GeForce GTX 6/7", "nvidia", r"\bgtx\s*[67]\d{2}\b", ("h264",), 35, "Feature coverage varies strongly by SKU."),
    GPUFamily("RTX workstation Ada", "nvidia", r"\brtx\s*(?:[2456]000|2000)\s*ada\b", ("h264", "hevc", "av1"), 95),
    GPUFamily("RTX workstation A", "nvidia", r"\brtx\s*a\s*\d{3,4}\b", ("h264", "hevc"), 85),
    GPUFamily("Quadro RTX", "nvidia", r"\bquadro\s+rtx\s*\d{3,4}\b", ("h264", "hevc"), 80),
    GPUFamily("Quadro P", "nvidia", r"\bquadro\s+p\s*\d{3,4}\b", ("h264", "hevc"), 60),
    GPUFamily("NVIDIA L4", "nvidia", r"\bnvidia\s+l4\b", ("h264", "hevc", "av1"), 95),
    GPUFamily("NVIDIA T4", "nvidia", r"\bnvidia\s+t4\b", ("h264", "hevc"), 80),
    # NOTE: Tesla A100/H100 and GT 1030 MUST NOT match a catch-all NVIDIA rule.

    # AMD: RX 6400 and RX 6500 XT lack hardware encode units. Excluded below.
    GPUFamily("Radeon RX 9000", "amd", r"\bradeon\s+(?:rx\s*)?9\d{3}\b", ("h264", "hevc", "av1"), 87),
    GPUFamily("Radeon RX 7000", "amd", r"\bradeon\s+(?:rx\s*)?7\d{3}\b", ("h264", "hevc", "av1"), 83),
    GPUFamily("Radeon RX 6000", "amd", r"\bradeon\s+(?:rx\s*)?6\d{3}\b", ("h264", "hevc"), 72),
    GPUFamily("Radeon RX 5000", "amd", r"\bradeon\s+(?:rx\s*)?5\d{3}\b", ("h264", "hevc"), 65),
    GPUFamily("Radeon RX 500", "amd", r"\bradeon\s+rx\s*5\d{2}\b", ("h264", "hevc"), 55),
    GPUFamily("Radeon RX 400", "amd", r"\bradeon\s+rx\s*4\d{2}\b", ("h264", "hevc"), 50),
    GPUFamily("Radeon RX Vega", "amd", r"\bradeon\s+(?:rx\s+)?vega\b", ("h264", "hevc"), 55),
    GPUFamily("Radeon 800M iGPU", "amd", r"\bradeon\s+8\d{2}m\b", ("h264", "hevc"), 60),
    GPUFamily("Radeon 700M iGPU", "amd", r"\bradeon\s+7\d{2}m\b", ("h264", "hevc"), 55),
    GPUFamily("Radeon 600M iGPU", "amd", r"\bradeon\s+6\d{2}m\b", ("h264", "hevc"), 50),
    GPUFamily("Radeon Pro W7000", "amd", r"\bradeon\s+pro\s+w7\d{3}\b", ("h264", "hevc", "av1"), 80),
    GPUFamily("Radeon Pro W6000", "amd", r"\bradeon\s+pro\s+w6\d{3}\b", ("h264", "hevc"), 70),
    GPUFamily("Radeon Pro WX", "amd", r"\bradeon\s+pro\s+wx\s*\d{3,4}\b", ("h264", "hevc"), 45),
    GPUFamily("Radeon integrated Vega", "amd", r"\bradeon\s+(?:vega\s*\d+|rx\s+vega\s*\d+)\b", ("h264", "hevc"), 43),
    GPUFamily("Radeon generic", "amd", r"\b(?:amd\s+)?radeon(?:\s+graphics)?\b", ("h264",), 25, "Exact model unknown; H.264 is only a probe candidate."),

    # Intel: no Quick Sync inferred from an Intel CPU name alone.
    GPUFamily("Intel Arc A", "intel", r"\barc(?:\s+pro)?\s+a\s*\d{3}[a-z]?\b", ("h264", "hevc", "av1"), 93),
    GPUFamily("Intel Arc B", "intel", r"\barc(?:\s+pro)?\s+b\s*\d{3}[a-z]?\b", ("h264", "hevc", "av1"), 96),
    GPUFamily("Intel Arc generic", "intel", r"\bintel\s+arc(?:\s+graphics)?\b", ("h264", "hevc"), 78, "Exact Arc model unknown; test AV1 separately after identification."),
    GPUFamily("Intel Iris Xe", "intel", r"\biris\s+xe\b", ("h264", "hevc"), 62),
    GPUFamily("Intel Iris Plus", "intel", r"\biris\s+plus\b", ("h264", "hevc"), 50),
    GPUFamily("Intel Iris Pro", "intel", r"\biris\s+pro\b", ("h264", "hevc"), 45),
    GPUFamily("Intel UHD 700", "intel", r"\buhd(?:\s+graphics)?\s*7\d{2}\b", ("h264", "hevc"), 58),
    GPUFamily("Intel UHD 600", "intel", r"\buhd(?:\s+graphics)?\s*6\d{2}\b", ("h264", "hevc"), 53),
    GPUFamily("Intel UHD generic", "intel", r"\bintel(?:\(r\))?\s+uhd(?:\s+graphics)?\b|\buhd\s+graphics\b", ("h264", "hevc"), 40),
    GPUFamily("Intel HD 500-630", "intel", r"\bhd(?:\s+graphics)?\s*(?:5\d{2}|6[123]\d)\b", ("h264", "hevc"), 43),
    GPUFamily("Intel HD 4000-5500", "intel", r"\bhd(?:\s+graphics)?\s*[45]\d{3}\b", ("h264",), 30),
    GPUFamily("Intel HD 2000-3000", "intel", r"\bhd(?:\s+graphics)?\s*[23]\d{3}\b", ("h264",), 20),
    GPUFamily("Intel HD generic", "intel", r"\bintel(?:\(r\))?\s+hd\s+graphics\b", ("h264",), 15),
)

# Explicit exclusions take precedence over vendor/family patterns. Missing here
# does not imply the GPU definitely supports NVENC/AMF/QSV.
GPU_WITHOUT_USABLE_ENCODER = (
    (re.compile(r"\b(?:radeon\s+)?rx\s*6400\b", re.I), "Radeon RX 6400: hardware video encoder absent."),
    (re.compile(r"\b(?:radeon\s+)?rx\s*6500\s*xt\b", re.I), "Radeon RX 6500 XT: hardware video encoder absent."),
    (re.compile(r"\b(?:geforce\s+)?gt\s*1030\b", re.I), "GeForce GT 1030: NVENC absent."),
    (re.compile(r"\bnvidia\s+(?:a100|h100)\b", re.I), "Datacenter accelerator: do not assume NVENC."),
)

CPU_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("Intel Core Ultra 9", "high", r"\bcore\s+ultra\s+9\b"),
    ("Intel Core Ultra 7", "mid-high", r"\bcore\s+ultra\s+7\b"),
    ("Intel Core Ultra 5", "mid", r"\bcore\s+ultra\s+5\b"),
    ("Intel Core i9", "high", r"\b(?:core\s*)?i9[-\s]?\d"),
    ("Intel Core i7", "mid-high", r"\b(?:core\s*)?i7[-\s]?\d"),
    ("Intel Core i5", "mid", r"\b(?:core\s*)?i5[-\s]?\d"),
    ("Intel Core i3", "entry", r"\b(?:core\s*)?i3[-\s]?\d"),
    ("Intel Xeon", "workstation", r"\bxeon\b"),
    ("Intel Pentium", "entry", r"\bpentium\b"),
    ("Intel Celeron", "entry", r"\bceleron\b"),
    ("Intel N-series", "entry", r"\bintel(?:\(r\))?\s+(?:processor\s+)?n\d{2,3}\b"),
    ("AMD Ryzen 9", "high", r"\bryzen\s*9\b"),
    ("AMD Ryzen 7", "mid-high", r"\bryzen\s*7\b"),
    ("AMD Ryzen 5", "mid", r"\bryzen\s*5\b"),
    ("AMD Ryzen 3", "entry", r"\bryzen\s*3\b"),
    ("AMD Threadripper", "workstation", r"\bthreadripper\b"),
    ("AMD EPYC", "server", r"\bepyc\b"),
    ("AMD Athlon", "entry", r"\bathlon\b"),
    ("AMD FX", "legacy", r"\b(?:amd\s+)?fx[-\s]?\d{4}\b"),
    ("Apple Silicon", "other", r"\bapple\s+m[1-9]\b"),
)


def _clean_name(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\((?:r|tm)\)", " ", str(value or ""), flags=re.I).replace("™", " ").replace("®", " ")).strip()


def _gpu_names(names: str | Sequence[str] | None) -> tuple[str, ...]:
    if names is None:
        return ()
    if isinstance(names, str):
        names = re.split(r"[,;\n|]+", names)
    return tuple(clean for name in names if (clean := _clean_name(name)))


@dataclass(frozen=True)
class Hardware:
    cpu: str
    gpus: tuple[str, ...]
    ram_gb: float | None = None
    logical_cores: int | None = None

    @classmethod
    def from_scanner(
        cls,
        cpu_name: str,
        gpu_names: str | Sequence[str] | None,
        ram_gb: float | None = None,
        logical_cores: int | None = None,
    ) -> "Hardware":
        if ram_gb is not None and ram_gb <= 0:
            raise ValueError("ram_gb must be positive")
        if logical_cores is not None and logical_cores < 1:
            raise ValueError("logical_cores must be positive")
        return cls(_clean_name(cpu_name), _gpu_names(gpu_names), ram_gb, logical_cores)


@dataclass(frozen=True)
class GPUInfo:
    name: str
    family: str
    vendor: str
    possible_codecs: tuple[str, ...]
    priority: int
    note: str


@dataclass(frozen=True)
class HardwareReport:
    cpu: str
    cpu_family: str
    cpu_class: str
    gpus: tuple[GPUInfo, ...]
    ram_gb: float | None
    logical_cores: int | None
    software_preset: str

    def to_dict(self) -> dict:
        return asdict(self)


def identify_gpu(name: str) -> GPUInfo:
    """Return candidate capabilities, NOT asserted actual hardware capabilities."""
    clean = _clean_name(name)
    for regex, reason in GPU_WITHOUT_USABLE_ENCODER:
        if regex.search(clean):
            return GPUInfo(clean, "Excluded model", "unknown", (), 0, reason)
    for family in GPU_CATALOG:
        if re.search(family.pattern, clean, re.I):
            return GPUInfo(clean, family.family, family.vendor,
                           family.possible_codecs, family.priority, family.note)
    return GPUInfo(clean, "Unrecognized", "unknown", (), 0,
                   "No safe hardware-encoder assumption for this model.")


def _software_preset(hardware: Hardware) -> str:
    """Approximate CPU preset for x264/x265; a throughput hint, not a benchmark."""
    cores = hardware.logical_cores
    ram = hardware.ram_gb
    if cores is None:
        cores = 4  # conservative when scanner has not supplied thread count
    if ram is not None and ram < 4:
        return "ultrafast"
    if cores <= 2:
        return "ultrafast"
    if cores <= 4 or (ram is not None and ram < 8):
        return "veryfast"
    if cores <= 8:
        return "fast"
    return "medium"


def describe_hardware(hardware: Hardware) -> HardwareReport:
    cpu_family, cpu_class = "Unknown CPU", "unknown"
    for family, category, regex in CPU_CATALOG:
        if re.search(regex, hardware.cpu, re.I):
            cpu_family, cpu_class = family, category
            break
    return HardwareReport(
        hardware.cpu, cpu_family, cpu_class,
        tuple(identify_gpu(name) for name in hardware.gpus),
        hardware.ram_gb, hardware.logical_cores, _software_preset(hardware),
    )


def _normalize_codec(codec: str) -> str:
    result = CODEC_ALIASES.get(codec.strip().casefold())
    if result is None:
        raise ValueError("codec must be h264, hevc/h265 or av1")
    return result


@lru_cache(maxsize=16)
def available_ffmpeg_encoders(ffmpeg_bin: str = "ffmpeg") -> frozenset[str]:
    """Read the current FFmpeg *build* encoder list; does not prove device support."""
    executable = shutil.which(ffmpeg_bin)
    if not executable:
        raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg_bin!r}")
    result = subprocess.run(
        [executable, "-hide_banner", "-encoders"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=12, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg -encoders failed: {result.stderr[-400:]}")
    names = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0].startswith("V"):
            names.add(parts[1])
    return frozenset(names)


def probe_ffmpeg_encoder(encoder: str, ffmpeg_bin: str = "ffmpeg", timeout: int = 15) -> tuple[bool, str]:
    """Encode ONE generated black frame; never opens the user's media files.

    This probes the FFmpeg default hardware device. On a multi-GPU system this
    may test a different physical adapter from the one matched in the catalogue.
    """
    approved = set(SOFTWARE_ENCODERS["h264"] + SOFTWARE_ENCODERS["hevc"]
                   + SOFTWARE_ENCODERS["av1"])
    approved.update(item for family in ENCODERS.values() for item in family.values())
    if encoder not in approved:
        raise ValueError(f"Encoder is not in the FFClass allowlist: {encoder!r}")
    executable = shutil.which(ffmpeg_bin)
    if not executable:
        return False, "FFmpeg executable not found"
    cmd = [
        executable, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=128x128:r=1:d=1",
        "-frames:v", "1", "-an", "-c:v", encoder,
        "-pix_fmt", "nv12" if encoder.endswith("_qsv") else "yuv420p",
        "-f", "null", "-",
    ]
    try:
        completed = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"One-frame test failed: {exc}"
    if completed.returncode:
        return False, f"Encoder failed (exit {completed.returncode}): {completed.stderr[-500:].strip()}"
    return True, "One-frame encoding passed on FFmpeg's default device"


@dataclass(frozen=True)
class Recommendation:
    codec: str
    encoder: str
    mode: str                   # 'hardware', 'software', or 'unverified'
    gpu_name: str | None
    ffmpeg_args: tuple[str, ...]
    verified: bool
    reason: str
    attempts: tuple[str, ...]   # useful to show in FFClass diagnostics

    def to_dict(self) -> dict:
        return asdict(self)


def _arguments(encoder: str, preset: str) -> tuple[str, ...]:
    # Avoid passing x264-only -preset values to AMF/QSV/NVENC: values differ.
    args = ("-c:v", encoder)
    if encoder in {"libx264", "libx265"}:
        args += ("-preset", preset, "-crf", "23" if encoder == "libx264" else "28")
    elif encoder == "libsvtav1":
        args += ("-crf", "35")
    elif encoder == "libaom-av1":
        args += ("-crf", "35", "-cpu-used", "6")
    return args


def recommend_encoder(
    hardware: Hardware,
    codec: str = "h264",
    *,
    verify: bool = True,
    ffmpeg_bin: str = "ffmpeg",
) -> Recommendation:
    """Choose encoder from GPU catalogue; verify one-frame run when requested.

    verify=True: FFmpeg is required, and available FFmpeg encoders + GPU encode
    are checked. verify=False: pure *unverified* catalogue suggestion, useful
    to display a UI recommendation before FFmpeg has been installed.
    """
    wanted = _normalize_codec(codec)
    report = describe_hardware(hardware)
    candidates: list[tuple[str, str | None]] = []
    for gpu in sorted(report.gpus, key=lambda item: -item.priority):
        if wanted in gpu.possible_codecs and gpu.vendor in ENCODERS:
            candidate = ENCODERS[gpu.vendor][wanted]
            # Do not test identical default-device encoders several times.
            if not any(name == candidate for name, _ in candidates):
                candidates.append((candidate, gpu.name))
    candidates.extend((name, None) for name in SOFTWARE_ENCODERS[wanted])

    if not verify:
        chosen, gpu_name = candidates[0]
        return Recommendation(wanted, chosen, "unverified", gpu_name,
                              _arguments(chosen, report.software_preset), False,
                              "Catalogue estimate only: run with verify=True before conversion.", ())

    installed = available_ffmpeg_encoders(ffmpeg_bin)
    attempts: list[str] = []
    for name, gpu_name in candidates:
        if name not in installed:
            attempts.append(f"{name}: missing from FFmpeg build")
            continue
        ok, detail = probe_ffmpeg_encoder(name, ffmpeg_bin=ffmpeg_bin)
        attempts.append(f"{name}: {detail}")
        if ok:
            mode = "hardware" if gpu_name else "software"
            return Recommendation(wanted, name, mode, gpu_name,
                                  _arguments(name, report.software_preset), True,
                                  detail + (" (default device; not GPU identity verification)" if gpu_name else ""),
                                  tuple(attempts))
    raise RuntimeError("No working encoder for " + wanted + ":\n" + "\n".join(attempts))


# Example integration (the example is intentionally NOT executed on import):
#   from hardware_db import Hardware, describe_hardware, recommend_encoder
#   hw = Hardware.from_scanner(cpu_name="Intel Core i5-12400F",
#                              gpu_names=["NVIDIA GeForce RTX 4060"],
#                              ram_gb=16, logical_cores=12)
#   report = describe_hardware(hw).to_dict()
#   choice = recommend_encoder(hw, "hevc", verify=True)
#   command = ["ffmpeg", "-nostdin", "-i", input_path,
#              *choice.ffmpeg_args, "-c:a", "copy", output_path]
#   # The caller owns actual transcoding and decides whether to invoke subprocess.
