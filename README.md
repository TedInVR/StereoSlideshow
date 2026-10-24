# Stereo Slideshow

A macOS desktop app for making stereoscopic photo/video slideshows, with
ordered music tracks, stereo captions, animated photos, titles and fades.
Exports full side-by-side MP4, red/cyan anaglyph MP4, and an optional
YouTube compatibility MKV. Version 0.26.

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
and preview an instrumental take or vocal song. **Use this music** adds it as the soundtrack.
The request includes full clips, title, opening, closing fade and black tail;
accepting a take uses visual-ending mode and disables photo Auto-Fit.

Requires a separately installed ACE-Step 1.5 engine with its REST API and
working dependencies/models. Choose the folder containing `acestep/api_server.py`
once. Both `python_embeded` and `python_embedded` portable Python folders are supported; dangling copied `.venv` links are skipped. The app can start its local API using that installation's Python;
an already-running API on `http://127.0.0.1:8001` works too. The Gradio browser
UI is a different service. Older installations may need an ACE-Step update.
No Suno account, paid API or cloud music service is used.

Takes are retained under Generated Music. Instrumental music longer than ten minutes uses matching
sections joined with crossfades. Exact timing is prepared with FFmpeg; model
style/quality and musical continuity vary. If the timeline changes, generate a
new take. See the bundled guide for details and cancellation behavior.

Integration tests use a local simulated ACE-Step API and real FFmpeg. Actual
model inference and Apple Silicon startup still need validation on a Mac.

Project source and future updates: https://github.com/TedInVR/StereoSlideshow

## Save a resumable project

Use **File → Save Project** (Command–S). A project folder beside the first visual
source (music fallback) contains a `.stereoslideshow` file and copies of the
imported media. Settings, order, captions and clip sound choices are saved.
**Open Project** (Command–Option–O) resumes from it; move the whole folder to
keep it portable. **Save Project As** (Command–Shift–S) creates a separate bundle.
Media copying uses background progress/cancellation and can require significant
space. Failed/cancelled saves keep the previous saved project file intact.

## Output filenames

`TITLE_StereoSlideshow_Full_SBS_3D_1080p_4min03sec.mp4`

Uses the title (or an eight-digit random prefix), chosen resolution and final
duration, rounded to seconds. Exact minutes use `4min`; under a minute uses
`44sec`. Anaglyph and optional compatibility MKV have distinct format tags.
Existing matching exports get a numbered title suffix instead of being replaced.

## Songs with vocals and saved descriptions

Music mode offers **Instrumental**, **Write a song about a topic**, and
**Use my lyrics**. Select vocal preference and language for songs. Topic mode
requires ACE-Step's language model; it generates words and music together.
Returned lyrics can be reviewed, edited and reused for another take. Supplied
lyrics are passed unchanged. Vocal songs support up to ten minutes in this
version; unusually short vocal results are not looped. Voice, delivery and
adherence to all words are model-dependent.

**Saved descriptions** includes seven user-supplied starter arrangements.
Load, edit, save under a name, update or remove a description. The editor's text
is retained on removal. Personal lists persist under Settings across projects
and app updates. Use **Genre → Use description only** for a detailed description
without adding a broad genre. Descriptions mentioning vocals should be used
with a song mode if singing is wanted. Projects retain the selected text and
song choices; they do not embed the entire personal saved-description list.

## Keep and edit audio takes

The music window lists previous takes and offers **Save Audio As…** (WAV,
FLAC or MP3) and **Import / reload audio…**, including external recordings.
Keep the companion JSON with exported audio to reload its lyrics and style.
Each edit produces a separate take. The source stays fixed until explicitly
replaced with the previewed result.

**What to do** offers selected-passage replacement, ending extension to the
slideshow duration, local trimming, and adding an instrument over the original.
Repaint results are spliced locally to preserve decoded audio outside the
selected region. Extensions retain the song except for a half-second join.
Added instruments use ACE-Step's **acestep-v15-base** Lego task and are mixed
with the original recording; the separate generated stem is also retained.
Base may download on first use. A separately running API must have Base loaded
for instrument generation. AI edits support source/result lengths up to ten
minutes. Model performance and musical fit need auditioning; model inference
for these new edit tasks requires testing on the Mac. See Help → User guide.

## Upload to YouTube

Use **File → Upload finished SBS video to YouTube…**, or the YouTube controls
in Export. Connect your channel using your own Google Desktop OAuth client;
enable YouTube Data API v3 and follow **Help → User guide → YouTube upload**.
Tokens use macOS Keychain. No shared OAuth credentials are included in this
repository. Client JSON, preferences, tokens and personal media must not be
committed. Testing clients may require reconnection after seven days.

Review the title, exact description, reusable template, tags, audience,
synthetic-content disclosure and Private/Unlisted/Public visibility. New uploads
default to Private. The automatic option authorizes one render only and resets.
A tagged stereo MKV upload copy is remuxed without re-encoding; ordinary Full-SBS
and anaglyph exports are retained. Interrupted chunks retry within the current
session. Closing/restarting the app does not resume an unfinished upload.

The offline OAuth/protocol and UI tests use simulated Google responses; actual
Mac sign-in, Keychain access and a Private test upload still need validation.
VR180 cinema and immersive footage are the next phase, not part of v0.24.

## Guided YouTube setup

**Help → Guided YouTube Setup…** provides eight resumable steps with Google
page links, exact field instructions, copyable scopes, JSON validation and a
handoff to the existing account connection. The uploader also offers the guide;
Connect opens it when no Desktop client is configured. Already-downloaded JSON
can skip directly to connection. Existing connections are kept.

Google-side actions remain manual. Progress checkboxes record what the user
completed, without claiming API verification. Local progress and credentials
are excluded from releases. A shared verified developer registration for a
simpler public-user Connect flow is not included in this release.

## Clearer audience choices

The YouTube uploader explains who the video targets, with **No — general
audience** and **Yes — content directed at children**, conditional guidance
for general-audience slideshows and **What does this mean?** help beside it.
The creator still chooses explicitly; guidance does not change the API setting.
