"""Caption-free project round trips, reversible visibility, and actual preview rendering."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtWidgets as Q,QtTest
 from PIL import Image
 import app,engine
 from project_bundle import save_project,read_project,new_project_path
 qt=Q.QApplication([]);main=app.Window();photo=Path(td)/'Filename must not appear.jpg';Image.new('RGB',(100,50),'red').save(photo);main.add([str(photo)])
 assert not main.captions_enabled.isChecked()
 snap=main.project_snapshot();assert snap['captions'][str(photo)]==''
 path=new_project_path(Path(td),'No captions');save_project(path,snap);main.restore_project(path,read_project(path));assert not main.captions_enabled.isChecked() and not any(main.captions.values())
 main.caption_names();texts=dict(main.captions);assert main.captions_enabled.isChecked() and any(texts.values())
 main.captions_enabled.setChecked(False);assert main.captions==texts
 path2=new_project_path(Path(td),'Hidden captions');save_project(path2,main.project_snapshot());main.restore_project(path2,read_project(path2));assert not main.captions_enabled.isChecked() and any(main.captions.values())
 main.captions_enabled.setChecked(True);assert any(main.captions.values())
 legacy=read_project(path2);legacy['settings'].pop('captions_enabled');main.restore_project(path2,legacy);assert not main.captions_enabled.isChecked() and any(main.captions.values())
 editor=app.CaptionEditor(['new.jpg'],{},True,main);assert editor.captions['new.jpg']=='';editor.reject()
 main.sec.setValue(1);main.pause.setValue(0);main.closing.setValue(0);main.title.setText('');seen=[];original=engine.caption_image
 def capture(text,*args):seen.append(text);return original(text,*args)
 with patch.object(engine,'caption_image',capture),patch.object(app.QtGui.QDesktopServices,'openUrl',return_value=True):
  for enabled in (False,True):
   seen.clear();main.captions_enabled.setChecked(enabled);main.begin(preview=True)
   for _ in range(10000):
    qt.processEvents();QtTest.QTest.qWait(5)
    if not main.worker.isRunning():qt.processEvents();break
   assert not main.worker.isRunning() and seen,main.status.text()
   assert any(seen)==enabled,(enabled,seen)
 main.project_dirty=False;main.close();qt.processEvents()
print('Caption round trips, legacy migration, filename opt-in, reversible toggle, and actual captioned/caption-free preview renders passed.')
