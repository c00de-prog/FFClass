# FFClass

FFClass is a Windows desktop app for local video processing. It helps people choose a task without writing FFmpeg commands by hand. The interface uses Python and PySide6; media processing happens on the user's computer.

## Current features

- First-run setup for a display name, language, and theme; PC details are saved as JSON.
- Video selection and drag and drop.
- Compression for sharing or storage, with quality and resolution options.
- Audio track repair, conversion, and removal.
- Remuxing to MP4 or MKV without re-encoding when the streams are compatible.
- A dedicated progress screen with percentage, estimated remaining time, cancellation, and a Home button.
- Recent output history and PC information. A hardware encoder is treated as a candidate; `libx264` remains available as a fallback.
- Russian and English interfaces, with dark and light themes.

Selecting a file reads only its name, size, and extension. After the user clicks **Start processing**, `ffprobe` reads detailed metadata and FFmpeg is checked and started. These processes do not run while the app is idle. The wizard is removed from the widget tree during processing and rebuilt when the user returns home. Actual RAM use depends on the operating system and Qt version.

## Project files

| File | Purpose |
| --- | --- |
| `gui.py` | Main window, preferences, and task wizard |
| `encoder.py` | Local FFmpeg/ffprobe execution, options, and progress |
| `processing_view.py` | Lightweight processing screen |
| `resource_manager.py` | Physical RAM detection without background polling |
| `stage_ffmpeg.py` | Checks and stages a local FFmpeg pair for packaging |
| `build_windows.py` | Builds a self-contained Windows app folder with PyInstaller |
| `config_storage.py`, `oscheck.py`, `hardware_db.py` | Existing configuration and PC detection modules |

## Run from source on Windows

Install the project's development dependencies, including `PySide6`, in your Python environment. From the project root, run:

```powershell
python gui.py
```

For media processing, put a matching `ffmpeg.exe` and `ffprobe.exe` pair in `bin/`. You can stage a pair from another local folder:

```powershell
python stage_ffmpeg.py --source "C:\path\to\ffmpeg\bin"
```

The staging script also creates `bin/ffclass_ffmpeg.json`, which the build script verifies. The `bin/` folder is prepared on the build machine. Whether it is committed to Git is a project choice; the build script requires it to be present locally.

## Build for Windows

After testing the source version, install `PyInstaller` in the development environment and run:

```powershell
python build_windows.py
```

The output is `dist/FFClass/`. Distribute the **entire folder**, not only `FFClass.exe`. End users do not need to install Python, a virtual environment, or FFmpeg separately. Build the Windows release on Windows.

Personal settings such as `pc_specs.json`, `ffclass_profile.json`, and `settings.json` should not be bundled with a public release. In the packaged app, settings are stored under `%LOCALAPPDATA%\FFClass`.

## Project status

The source version has been tested on Windows. Building and testing the standalone `dist/FFClass/` release on another Windows computer is the next step.
