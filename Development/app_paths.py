"""All program files live under one permanent project folder."""
import os
from pathlib import Path
ROOT=Path(os.environ.get('STEREO_SLIDESHOW_HOME',str(Path(__file__).resolve().parent.parent))).expanduser().resolve()
SETTINGS=ROOT/'Settings'/'settings.json'
ICON=ROOT/'Stereo Slideshow.app'/'Contents'/'Resources'/'StereoSlideshow.png'
VERSION='0.22'
