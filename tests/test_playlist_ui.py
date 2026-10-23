import os,sys,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from PySide6 import QtCore,QtWidgets as Q
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 import app
 from organizer import Organizer,paths,move_selected
 from walkthrough import Walkthrough
 qt=Q.QApplication([]);main=app.Window()
 for p,d in [('/a/First.wav',100),('/a/Second.wav',143),('/a/clip.mp4',30)]:main._duration_cache[p]=(None,d,'')
 main.add(['/a/Mom.jpg','/a/Trip.jpg','/a/clip.mp4','/a/First.wav','/a/Second.wav'])
 assert main.playlist()==['/a/First.wav','/a/Second.wav']
 assert '4:03 (243 seconds)' in main.music.text()
 main.fit_music.setChecked(True);main.refresh_timing();assert main.end_mode.currentIndex()==1 and not main.sec.isEnabled()
 assert '2 photos' in main.timing_summary.text() and 'Finished video: 4:03' in main.timing_summary.text()
 dialog=Organizer(main);dialog.showMaximized();qt.processEvents()
 assert dialog.isMaximized() and dialog.content.count()==3 and dialog.music.count()==2
 dialog.music.item(1).setSelected(True);move_selected(dialog.music,-1)
 assert paths(dialog.music)==['/a/Second.wav','/a/First.wav']
 assert main.playlist()==['/a/First.wav','/a/Second.wav']
 dialog.apply();dialog.reject();assert main.playlist()==['/a/Second.wav','/a/First.wav']
 dialog2=Organizer(main);dialog2.music.clear();dialog2.reject();assert len(main.playlist())==2
 wizard=Walkthrough(main,app.CaptionEditor);wizard.show();qt.processEvents()
 assert paths(wizard.playlist)==main.playlist()
 wizard.page(4).check=lambda:True
 for i in range(5):wizard.next();qt.processEvents()
 assert wizard.currentId()==5
 assert 'Finished video: 4:03' in wizard.review.toPlainText()
 wizard.cleanup();wizard.reject()
 main.show();qt.processEvents();None
 dialog3=Organizer(main);dialog3.showMaximized();qt.processEvents();None;dialog3.reject()
 main.end_mode.setCurrentIndex(0);assert not main.fit_music.isChecked() and main.sec.isEnabled()
 for w in qt.topLevelWidgets():w.close()
 qt.processEvents()
 print('Qt tests passed: multiple tracks/durations, expanded organizer, reordering and Cancel isolation, timing calculation, endpoint controls, and walkthrough playlist preservation.')
