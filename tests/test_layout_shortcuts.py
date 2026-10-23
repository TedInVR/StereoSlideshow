import os,sys,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtGui,QtWidgets as Q,QtTest
 import app
 from organizer import Organizer
 from shortcuts import ShortcutManager
 qt=Q.QApplication([]);main=app.Window();main.show();qt.processEvents()
 assert main.files.height()>main.files.width() and main.files.mapTo(main,QtCore.QPoint()).x()<main.sec.mapTo(main,QtCore.QPoint()).x()
 assert main.bar.isHidden() and not hasattr(main,'auto')
 main.sec.setValue(7);main.add(['/a/photo.jpg','/a/song.wav']);main._duration_cache['/a/song.wav']=(None,100,'')
 main.fit_music.setChecked(True);main.refresh_timing();assert main.sec.value()==93 and not main.sec.isEnabled()
 main.fit_music.setChecked(False);assert main.sec.value()==7 and main.sec.isEnabled()
 dialog=Organizer(main);dialog.show();dialog.activateWindow();qt.processEvents();QtTest.QTest.keyClick(dialog,QtCore.Qt.Key_W,QtCore.Qt.ControlModifier);qt.processEvents();assert dialog.result()==Q.QDialog.Accepted and not dialog.isVisible()
 keys={name:main.shortcuts.sequence(name).toString(QtGui.QKeySequence.PortableText) for name in __import__('shortcuts').ACTIONS};keys['close']='Ctrl+Shift+W';main.shortcuts.save(keys)
 assert ShortcutManager(Path(td)/'Settings/shortcuts.json').sequence('close')==QtGui.QKeySequence('Ctrl+Shift+W')
 dialog=Organizer(main);dialog.show();dialog.activateWindow();qt.processEvents();QtTest.QTest.keyClick(dialog,QtCore.Qt.Key_W,QtCore.Qt.ControlModifier|QtCore.Qt.ShiftModifier);qt.processEvents();assert dialog.result()==Q.QDialog.Accepted and not dialog.isVisible()
 main.close();qt.processEvents();print('Layout, calculated timing/manual restoration, hidden idle progress, organizer close and persistent custom shortcuts passed.')
