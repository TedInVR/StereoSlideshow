import os,sys,tempfile,threading,subprocess,json
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtWidgets as Q,QtTest
 import music_dialog as m
 from engine import binary
 qt=Q.QApplication([]);root=Path(td);source=root/'song.flac'
 subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','sine=duration=4','-ac','2',str(source)],check=True)
 source.with_suffix('.json').write_text(json.dumps({'style':{'details':'My lovely arrangement','music_mode':'lyrics','lyrics':'Old words'},'lyrics':'Old words'}))
 def wait(dialog):
  for _ in range(500):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy() and dialog.generate.isEnabled():return
  raise AssertionError('worker did not finish')
 d=m.MusicDialog(6);d.show();qt.processEvents();assert not d.save_audio_button.isEnabled()
 with patch.object(Q.QFileDialog,'getOpenFileName',return_value=(str(source),'')):d.import_audio()
 wait(d);assert d.source_seconds==4 and d.source_path!=str(source) and d.lyrics.toPlainText()=='Old words' and d.mode.currentData()=='lyrics' and d.save_audio_button.isEnabled()
 previous=d.source_path;d.operation.setCurrentIndex(d.operation.findData('repaint'));qt.processEvents();assert d.range_widget.isVisible() and not d.instrument.isVisible()
 d.edit_start.setValue(1);d.edit_end.setValue(2)
 seen=[]
 def fake(options,seconds,output,cancel,status):
  seen.append(options);Path(output).write_bytes(Path(options['source_audio']).read_bytes());Path(output).with_suffix('.json').write_text(json.dumps({'requested_seconds':4,'style':d.style_options()}));return str(output)
 with patch.object(m,'edit_soundtrack',fake):d.begin();wait(d)
 assert seen[-1]['operation']=='repaint' and seen[-1]['edit_start']==1 and seen[-1]['edit_end']==2 and d.source_path==previous and d.result_path!=previous
 assert d.generate.mapTo(d,QtCore.QPoint(0,d.generate.height())).y()<d.height()
 d.use_result_source();assert d.source_path==d.result_path
 d.operation.setCurrentIndex(d.operation.findData('layer'));qt.processEvents();assert d.instrument.isVisible() and not d.range_widget.isVisible()
 export=root/'My keeper.wav'
 with patch.object(Q.QFileDialog,'getSaveFileName',return_value=(str(export),'WAV audio (*.wav)')):d.save_audio()
 wait(d);assert export.exists() and export.with_suffix('.json').exists() and d.result_path!=str(export)
 d.grab().save(str(Path(__file__).resolve().parents[3]/'build/audio_workbench_dialog.png'));d.reject()
 reopened=m.MusicDialog(6);assert reopened.takes.count()==2;reopened.load_selected_take();assert reopened.source_path and reopened.play.isEnabled();reopened.reject()
 print('Audio UI: asynchronous import/export, saved-take loading, lyric/style restore, edit range/instrument controls, retained editing source, preview/use and visible actions passed.')
