"""Planner selection, focused/custom briefs and legacy style recovery."""
import os,sys,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtWidgets as Q
 from music_generator import generation_request,make_prompt,GENRES
 from music_dialog import MusicDialog
 q=Q.QApplication([]);d=MusicDialog(120)
 assert d.planning.isChecked() and not d.era_toggle.isChecked() and not d.genre.isEditable()
 options=dict(d.style_options(),music_planning=True)
 request=generation_request(options,120);assert request['thinking'] and request['lyrics']=='[Instrumental]' and 'fingerpicked' in request['prompt']
 assert not generation_request(dict(options,music_planning=False),120)['thinking']
 assert generation_request(dict(options,music_mode='topic',topic='Family memories',music_planning=False),120)['thinking']
 prompt=make_prompt('1920s','Use description only','Dramatic and cinematic','Gentle piano trio')
 assert '1920' not in prompt and 'cinematic' not in prompt and 'Gentle piano trio' in prompt
 d.saved_descriptions.setCurrentIndex(1);d.load_description(1)
 assert d.genre.currentText()=='Use description only' and d.era.currentText()=='Any era'
 assert len(GENRES)==6 and 'Music box / fairground' not in GENRES and 'Barbershop harmony' not in GENRES
 d.reject()
print('Default planner, direct opt-out, mandatory topic planning, focused instrumental brief and description-only isolation passed.')
