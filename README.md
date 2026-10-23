# Stereo Slideshow

A macOS desktop app for making stereoscopic photo/video slideshows, with
ordered music tracks, stereo captions, animated photos, titles and fades.
Exports full side-by-side MP4, red/cyan anaglyph MP4, and an optional
YouTube compatibility MKV. Version 0.17.

## Install or update on a Mac

1. Quit Stereo Slideshow.
2. Download this repository with **Code → Download ZIP**, then extract it.
3. Double-click **Install or Update.command** inside the extracted folder.
4. Open your permanent Stereo Slideshow app in Applications. Keep using its
   existing icon after updates. The installer carries forward preferences.

Python 3.9–3.14 is required. FFmpeg and ffprobe must also be installed (for example, with Homebrew: `brew install ffmpeg`). The installer sets up the Python runtime and app dependencies; follow any messages it displays. The application is
currently unsigned. If macOS blocks the launcher, use Finder's Open command
or the Open Anyway option in System Settings after reviewing the source.

## Use

Drop photos, SBS video clips and optional music into the main window.
Arrange the visual sequence on the left and the ordered music on the right.
Follow the numbered settings groups, then click Create slideshow.
Help contains the user guide, guided walkthrough and editable shortcuts.
The wheel scrolls the settings pane without altering dropdowns or number fields.

**Zoom and pan** alternates close-up zooms (which crop image edges) with large
side-moving or vertically moving photos. **Subtle zoom and pan** keeps the
whole photo visible with a 2% zoom change and small travel. Pan distance applies
only to the subtle mode. Saved choices from older versions are retained.

## Development

Source is in `Development/`; the permanent macOS launcher and icon are in
`Stereo Slideshow.app/`. Runtime, Settings, Logs and Updates are local-only.
Do not commit personal media, captions, logs or generated videos.
Install dependencies from `Development/requirements.txt`; rendering also uses
FFmpeg/ffprobe. Run `python Development/app.py` for development. On Linux,
Qt UI checks can use `QT_QPA_PLATFORM=offscreen` (not a macOS packaging test).

The bundled guide describes stereo input formats, timing, audio and outputs.
Release notes are in `Development/Release_Notes.txt`. Test scripts are in
`tests/`; run them from the repository root. Rendering tests also require NumPy. Packaging uses
`tools/package_release.py`, which refreshes manifest hashes and creates a ZIP.

This private repository is the project source for future updates. Collaborators
need repository access; a private repository is not a public download page.
