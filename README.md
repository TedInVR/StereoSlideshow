# Stereo Slideshow

A macOS desktop app for making stereoscopic photo/video slideshows, with
ordered music tracks, stereo captions, animated photos, titles and fades.
Exports full side-by-side MP4, red/cyan anaglyph MP4, and an optional
YouTube compatibility MKV. Version 0.20.

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

## Create a soundtrack locally

In the Music step, choose **Create music to fit this slideshow…**. Select era,
genre and mood, optionally describe instruments or atmosphere, then generate
and preview an instrumental take. **Use this music** adds it as the soundtrack.
The request includes full clips, title, opening, closing fade and black tail;
accepting a take uses visual-ending mode and disables photo Auto-Fit.

Requires a separately installed ACE-Step 1.5 engine with its REST API and
working dependencies/models. Choose the folder containing `acestep/api_server.py`
once. Both `python_embeded` and `python_embedded` portable Python folders are supported; dangling copied `.venv` links are skipped. The app can start its local API using that installation's Python;
an already-running API on `http://127.0.0.1:8001` works too. The Gradio browser
UI is a different service. Older installations may need an ACE-Step update.
No Suno account, paid API or cloud music service is used.

Takes are retained under Generated Music. Longer than ten minutes uses matching
sections joined with crossfades. Exact timing is prepared with FFmpeg; model
style/quality and musical continuity vary. If the timeline changes, generate a
new take. See the bundled guide for details and cancellation behavior.

Integration tests use a local simulated ACE-Step API and real FFmpeg. Actual
model inference and Apple Silicon startup still need validation on a Mac.

Project source and future updates: https://github.com/TedInVR/StereoSlideshow
