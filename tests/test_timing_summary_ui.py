import os,sys,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtGui,QtWidgets as Q
 import app
 qt=Q.QApplication([]);main=app.Window();main.add(['/a/1.jpg','/a/2.jpg','/a/3.jpg','/a/4.jpg']);main.sec.setValue(20);main.closing.setValue(11);main.title.setText('A title');main.refresh_timing();main.show();qt.processEvents()
 summary=main.timing_summary
 assert summary.isReadOnly() and 'Finished video:' in summary.toPlainText()
 for width,height,font_size in [(1180,850,13),(900,650,18),(1180,850,13)]:
  main.resize(width,height);font=summary.font();font.setPointSize(font_size);summary.setFont(font);qt.processEvents()
  assert summary.height()>=summary.fontMetrics().lineSpacing()*8
  assert summary.height()==summary.minimumHeight()==summary.maximumHeight()
 # If a narrow pane or additional detail exceeds its space, every line remains scrollable.
 summary.setText('\n'.join('Timing detail '+str(i) for i in range(30)));qt.processEvents()
 assert summary.verticalScrollBar().maximum()>0
 viewport=summary.viewport();point=QtCore.QPointF(viewport.rect().center())
 event=QtGui.QWheelEvent(point,QtCore.QPointF(viewport.mapToGlobal(point.toPoint())),QtCore.QPoint(),QtCore.QPoint(0,-120),QtCore.Qt.NoButton,QtCore.Qt.NoModifier,QtCore.Qt.ScrollUpdate,False)
 Q.QApplication.sendEvent(viewport,event);assert summary.verticalScrollBar().value()>0
 summary.verticalScrollBar().setValue(summary.verticalScrollBar().maximum());assert summary.verticalScrollBar().value()==summary.verticalScrollBar().maximum()
 main.refresh_timing();qt.processEvents();main.grab().save(str(Path(__file__).resolve().parents[3]/'build/timing_summary_fixed.png'));main.close();qt.processEvents()
 print('Timing summary: readable reserved height at multiple sizes/fonts, all calculations retained, overflow scrollable by wheel, and last line accessible.')
