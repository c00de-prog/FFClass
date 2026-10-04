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
| `START_HERE.txt`, `Remove FFClass.cmd`, `remove_ffclass.ps1` | Portable ZIP guide and optional removal of the portable app and local settings |
| `installer.iss`, `build_installer.py` | Package the app folder as a Windows installer with Inno Setup |
| `run_ffclass.cmd` | Source launcher and build menu |
| `config_storage.py`, `oscheck.py`, `hardware_db.py` | Existing configuration and PC detection modules |

## Install or run FFClass on Windows

### 1. Portable ZIP (current release)

Download `FFClass-Windows.zip` from the GitHub release **Assets**. Extract the whole archive and launch `FFClass/FFClass.exe`. Keep its `_internal` folder beside the EXE. `FFClass/START_HERE.txt` contains quick instructions in English and Russian. Python, PySide6, FFmpeg, and ffprobe are bundled. This is a portable app; it does not register itself in Windows Installed apps.

To remove the portable app **and its settings**, close FFClass and run `FFClass/Remove FFClass.cmd`. It asks for confirmation, then removes the extracted app folder and `%LOCALAPPDATA%\FFClass`. Move any personal files out of the FFClass folder first. Videos outside that folder are not removed. You can also manually delete those two folders.

### 2. Optional Windows installer (future)

The project also has Inno Setup build scripts for a traditional installer with Start menu and Windows Installed apps integration. Publish this separately only after testing its installation and uninstallation.

### 3. Run from this repository

If a packaged app does not work on your PC, download or clone the repository and double-click `run_ffclass.cmd`. Select **1** to run from source. The launcher creates `.venv`, installs `requirements.txt` if PySide6 is missing, and starts FFClass. Later runs reuse the environment. Select **2** to build the installer yourself or **3** for the portable ZIP.

This path requires **Python 3 installed on Windows** and internet access for the initial Python package installation. The launcher looks for `bin/ffmpeg.exe` and `bin/ffprobe.exe`; if they are missing, it tries to stage a matching pair already installed on the PC. Without either pair, the UI can open but video processing is unavailable. A `.cmd` file cannot run Python code without an interpreter.

To prepare a verified pair manually in a development checkout:

```powershell
python stage_ffmpeg.py --source "C:\path\to\ffmpeg\bin"
```

This also creates `bin/ffclass_ffmpeg.json`, which the build script verifies.

## Build and publish from Windows

On a Windows build machine, prepare the local FFmpeg pair as above. Double-click `run_ffclass.cmd` and select **3**, or install `requirements.txt` and `requirements-build.txt` in your development environment and run `python build_windows.py`. No Inno Setup installation is required for the ZIP.

The build creates `dist/FFClass/` and `dist/FFClass-Windows.zip`, including the quick guide and removal scripts. Test the extracted ZIP on another Windows computer: launch FFClass, process a short video, and verify removal with no personal files inside the FFClass folder. Then create a GitHub Release with a version tag (for example, `v0.1.0`) and attach `dist/FFClass-Windows.zip` under **Assets**. The automatically generated repository "Source code (zip)" download is not the packaged Windows app.

To build the optional installer later, install [Inno Setup](https://jrsoftware.org/isinfo.php), select **2** in `run_ffclass.cmd`, and test `dist/FFClass-Setup-0.1.0-Windows.exe` separately. An unsigned EXE may show a Microsoft Defender SmartScreen warning; signing and reputation are separate release concerns.

Personal settings such as `pc_specs.json`, `ffclass_profile.json`, and `settings.json` should not be bundled with a public release. In the packaged app, settings are stored under `%LOCALAPPDATA%\FFClass`.

## Project status

Test the ZIP produced by this revision on another Windows computer before publishing it.

## Third-party software

FFClass is not affiliated with or endorsed by the FFmpeg project or The Qt Company.

### FFmpeg

The Windows release bundles `ffmpeg.exe` and `ffprobe.exe` from FFmpeg.

- Version: [9.0.1 or 9.0.2 — confirm with `ffmpeg.exe -version`]
- Build obtained from: [download page URL]
- License of this build: [LGPL v2.1+ or GPL v2+ — see the `configuration:` line of `ffmpeg.exe -version`]
- Source code for this version: [URL to the matching source archive]
- License text: see `licenses/FFmpeg-LICENSE.txt` in the release folder

FFmpeg is run as a separate program; FFClass does not link against it. FFmpeg is a trademark of Fabrice Bellard, originator of the FFmpeg project.

### PySide6 / Qt

The interface uses PySide6 (Qt for Python), licensed under the LGPL v3. License information: <https://doc.qt.io/qtforpython-6/licenses.html>