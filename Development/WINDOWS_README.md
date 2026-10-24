# Stereo Slideshow for Windows — EXPERIMENTAL / UNTESTED

This is the Windows source-installer edition. **It has not been installed or
run on a real Windows computer.** Automated checks run in a non-Windows
environment. Please do not describe this edition as verified Windows support.
You may encounter installation, rendering, audio, authorization or update bugs.
There is currently no standalone Windows EXE/MSI installer or bundled Python.

## Intended requirements

- Windows 10 or 11, 64-bit (x64 is the intended initial target).
- 64-bit Python 3.10–3.14 installed from https://www.python.org/downloads/windows/.
  Python 3.12 is a conservative choice. Include the Python launcher/PATH option.
- FFmpeg and FFprobe on PATH. The official FFmpeg download page links Windows
  builds: https://ffmpeg.org/download.html#build-windows. Extract a build and add
  its `bin` folder (containing ffmpeg.exe and ffprobe.exe) to your user PATH.
  Open a new terminal and check `ffmpeg -version` and `ffprobe -version`.
- Internet access for the initial Python dependency installation and updates.

## Install

1. On the GitHub repository choose **Code → Download ZIP** and extract it.
2. Open the **Development** folder and double-click **Install-Windows.cmd**.
3. Read the console output. The installer creates a private Python environment
   and installs the app under `%LOCALAPPDATA%\Programs\Stereo Slideshow`.
4. Use **Stereo Slideshow (Experimental)** on the Desktop or Start menu.
5. After a successful launch you may delete the downloaded ZIP/extracted folder.
   Keep the permanent installation and all your source media/projects.

No administrator installation is intended. The PowerShell script creates two
shortcuts; execution-policy bypass applies to this one invocation, not a system
policy change. If your organization blocks scripts, do not bypass its rules.
The program is unsigned; review the source before choosing whether to run it.

## Features and limitations

The shared interface and engine provide stereo photos/videos, captions, ordered
music, previews, MP4/anaglyph output, project saving and Resolve source export.
These are implemented, **not verified on Windows**. Preview playback uses the
default associated video player. SBS needs a suitable stereo viewer; anaglyph
needs red/cyan glasses. Basic rendering does not require a separate AI model.

YouTube uses your own Google OAuth configuration and Windows Credential Manager,
with no plaintext-token fallback. No developer account credentials are included.
The existing upload workflow still prepares a tagged MKV; this edition does not
add YouTube stereo metadata to the ordinary Full-SBS MP4.

ACE-Step is optional and separately installed. Windows virtual environments and
portable interpreter paths are recognized, or an already-running local REST API
can be used. Its models, GPU drivers and AI performance have **not** been tested
here; there is no promise that every PC can generate music. You can use ordinary
audio files without ACE-Step.

## Updates and problem reports

Version 0.32 registers a per-user background scheduled task on first launch. It checks roughly every 15 minutes while logged in and installs only while the app is closed. Help → Automatically update while app is closed turns it off. Use **Help → Check for Updates** for manual checking. Windows installation, process waiting, restart
and secure credentials have Windows-specific implementations but remain untested
on that OS. Keep your project saved before installing an update. Re-running the
source installer is a recovery option. Mac and Windows use the same repository.

Report problems at https://github.com/TedInVR/StereoSlideshow/issues with Windows
version, Python version, app version and the error text. Diagnostics are under
the installed folder's **Logs** directory; the launcher writes `app.log` and the
updater writes `update.log`. Remove personal filenames or other sensitive details
before sharing logs. Never post your Google client JSON, tokens or account files.
