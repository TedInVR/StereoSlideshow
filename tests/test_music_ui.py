import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtWidgets as Q,QtTest
 import app,music_dialog
 qt=Q.QApplication([]);main=app.Window();main.add(['/photos/one.jpg','/photos/two.jpg','/clips/short.mp4'])
 main._duration_cache['/clips/short.mp4']=(None,30,'');main.sec.setValue(7);main.title.setText('Our trip');main.title_sec.setValue(6);main.pause.setValue(1);main.closing.setValue(6)
 # Main-window action snapshots all clips and overhead without depending on music length.
 seen=[]
 class Dialog:
  def __init__(self,seconds,parent):seen.append(seconds);self.result_path='/generated/score.wav'
  def exec(self):return Q.QDialog.Accepted
 with patch.object(music_dialog,'MusicDialog',Dialog):main.create_music()
 assert seen==[58] and main.playlist()==['/generated/score.wav'] and main.end_mode.currentIndex()==0 and not main.fit_music.isChecked() and main.sec.value()==7
 from walkthrough import Walkthrough
 wizard=Walkthrough(main,app.CaptionEditor)
 with patch.object(music_dialog,'MusicDialog',Dialog):wizard.create_music()
 assert seen==[58,58] and wizard.playlist.count()==1 and main.playlist()==['/generated/score.wav']
 wizard.cleanup();wizard.reject()
 # Generate asynchronously, retain earlier takes, and don't replace playlist until Use.
 def fake_generate(options,seconds,output,cancel,status):
  status('Testing generation…');Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_bytes(b'test');return str(output)
 with patch.object(music_dialog,'generate_soundtrack',fake_generate),patch.object(music_dialog,'find_installation',lambda:''):
  dialog=music_dialog.MusicDialog(58,main);dialog.show();dialog.begin()
  for _ in range(100):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy() and dialog.use.isEnabled():break
  assert dialog.use.isEnabled() and dialog.play.isEnabled() and dialog.progress.isHidden() and main.playlist()==['/generated/score.wav']
  first=dialog.result_path;dialog.begin()
  for _ in range(100):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy() and dialog.use.isEnabled():break
  assert dialog.result_path!=first and Path(first).exists();dialog.accept()
 # A slow job stays alive when Cancel/close requests cancellation; no destroyed QThread.
 def cancelled(options,seconds,output,cancel,status):
  cancel.wait(2);raise music_dialog.MusicCancelled()
 with patch.object(music_dialog,'generate_soundtrack',cancelled),patch.object(music_dialog,'find_installation',lambda:''):
  dialog=music_dialog.MusicDialog(58,main);dialog.show();dialog.begin();dialog.reject();assert dialog.isVisible()
  for _ in range(100):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy() and dialog.generate.isEnabled():break
  assert not dialog.busy() and not dialog.use.isEnabled();dialog.reject()
 main.close();qt.processEvents();print('Music UI: visual duration with full clips/title/fade, playlist acceptance, asynchronous generation, preview availability, take retention and safe cancellation passed.')
