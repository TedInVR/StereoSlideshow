import os,sys,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtGui,QtWidgets as Q
 import app
 from walkthrough import Walkthrough
 qt=Q.QApplication([]);main=app.Window();main.show();qt.processEvents()
 def wheel(control):
  pos=QtCore.QPointF(control.rect().center());globalpos=QtCore.QPointF(control.mapToGlobal(pos.toPoint()))
  event=QtGui.QWheelEvent(pos,globalpos,QtCore.QPoint(),QtCore.QPoint(0,-120),QtCore.Qt.NoButton,QtCore.Qt.NoModifier,QtCore.Qt.ScrollUpdate,False)
  Q.QApplication.sendEvent(control,event);qt.processEvents()
 scroll=main.end_mode.parentWidget()
 while not isinstance(scroll,Q.QScrollArea):scroll=scroll.parentWidget()
 bar=scroll.verticalScrollBar();bar.setValue(0);before=main.end_mode.currentIndex();main.end_mode.setFocus();wheel(main.end_mode)
 assert main.end_mode.currentIndex()==before and bar.value()>0
 bar.setValue(0);before=main.sec.value();main.sec.setFocus();wheel(main.sec);assert main.sec.value()==before and bar.value()>0
 main.animation.setCurrentIndex(1);assert main.drift.isEnabled();main.animation.setCurrentIndex(0);assert not main.drift.isEnabled()
 # Intentional keyboard changes remain available, even though wheel edits are blocked.
 from PySide6.QtTest import QTest
 main.animation.setFocus();QTest.keyClick(main.animation,QtCore.Qt.Key_Down);assert main.animation.currentIndex()==1
 wizard=Walkthrough(main,app.CaptionEditor);wizard.show();qt.processEvents();before=wizard.controls['animation'].currentIndex();wheel(wizard.controls['animation']);assert wizard.controls['animation'].currentIndex()==before
 wizard.cleanup();wizard.reject();main.close();qt.processEvents();print('Wheel over focused dropdowns/numeric fields scrolls settings without changing values; walkthrough protected; explicit selection remains available.')
