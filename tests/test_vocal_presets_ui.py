import os,sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtWidgets as Q,QtTest
 import app,music_dialog
 from description_presets import DEFAULT_DESCRIPTIONS
 qt=Q.QApplication([]);main=app.Window();dialog=music_dialog.MusicDialog(63,main);dialog.show();qt.processEvents()
 assert dialog.mode.currentData()=='instrumental' and not dialog.vocal_panel.isVisible() and dialog.saved_descriptions.count()==8
 name=next(iter(DEFAULT_DESCRIPTIONS));index=dialog.saved_descriptions.findData(name);dialog.saved_descriptions.setCurrentIndex(index);dialog.load_description(index)
 assert dialog.details.toPlainText()==DEFAULT_DESCRIPTIONS[name] and 'mentions vocals' in dialog.status.text()
 text='Velvety piano, warm brass.\nPlayful guitar with bright rhythmic surprises.';dialog.details.setPlainText(text)
 with patch.object(Q.QInputDialog,'getText',return_value=('My favorite arrangement',True)):dialog.save_description()
 assert dialog.description_presets.load()['My favorite arrangement']==text
 dialog.details.setPlainText('Previous text');index=dialog.saved_descriptions.findData('My favorite arrangement');dialog.load_description(index);assert dialog.details.toPlainText()==text;dialog.details.undo();assert dialog.details.toPlainText()=='Previous text'
 dialog.mode.setCurrentIndex(1);qt.processEvents();assert dialog.vocal_panel.isVisible() and dialog.topic.isVisible() and dialog.lyrics.isReadOnly()
 dialog.begin();assert not dialog.busy() and 'subject' in dialog.status.text()
 words='[Verse 1]\nWhalom Park in summer sunshine\n[Chorus]\nTake me home again'
 options_seen=[]
 def fake(options,seconds,output,cancel,status):
  options_seen.append(options);Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_bytes(b'fake');Path(output).with_suffix('.json').write_text(json.dumps({'mode':options['music_mode'],'lyrics':words}));return str(output)
 dialog.topic.setPlainText('Whalom Park memories');dialog.voice.setCurrentText('Female lead')
 with patch.object(music_dialog,'generate_soundtrack',fake):
  dialog.begin()
  for _ in range(200):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy() and dialog.use.isEnabled():break
 assert options_seen[0]['music_mode']=='topic' and options_seen[0]['voice']=='Female lead' and dialog.lyrics.toPlainText()==words and main.project_music_style['lyrics']==words
 dialog.edit_generated.click();assert dialog.mode.currentData()=='lyrics' and not dialog.lyrics.isReadOnly() and dialog.lyrics.toPlainText()==words
 assert dialog.generate.mapTo(dialog,QtCore.QPoint(0,dialog.generate.height())).y()<dialog.height()
 dialog.grab().save(str(Path(__file__).resolve().parents[3]/'build/vocal_presets_dialog.png'));dialog.reject()
 again=music_dialog.MusicDialog(63,main);assert again.mode.currentData()=='topic' and again.lyrics.toPlainText()==words and again.saved_descriptions.findData('My favorite arrangement')>=0
 index=again.saved_descriptions.findData('My favorite arrangement');again.saved_descriptions.setCurrentIndex(index);again.load_description(index)
 with patch.object(Q.QMessageBox,'question',return_value=Q.QMessageBox.Yes):again.remove_description()
 assert 'My favorite arrangement' not in again.description_presets.load() and again.details.toPlainText()==text
 again.reject()
 from walkthrough import Walkthrough
 before=dict(main.project_music_style);wizard=Walkthrough(main,app.CaptionEditor);staged=music_dialog.MusicDialog(63,wizard);staged.mode.setCurrentIndex(2);staged.lyrics.setPlainText('New draft');staged.remember_style(staged.style_options());assert main.project_music_style==before and wizard.project_music_style['lyrics']=='New draft';staged.reject();wizard.cleanup();wizard.reject()
 main.close();qt.processEvents()
 print('Music modes/validation, topic lyric review and edit reuse, seven starters, saved description load/undo/remove, persistence, project style and visible action buttons passed.')
