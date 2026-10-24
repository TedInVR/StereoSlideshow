import os,sys,json,tempfile,copy
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtWidgets as Q,QtTest
 import app,youtube_dialog as d,youtube_upload as y
 class Store:
  value=dict(channel={'id':'channel-one','title':'Ted in VR'})
  def load(self):return copy.deepcopy(self.value)
  def save(self,x):self.value=x
  def delete(self):self.value=None
 store=Store();calls=[]
 class Client:
  def __init__(self):self.store=store
  def upload(self,path,plan,cancel,status,progress):
   calls.append((path,plan));return {'id':'VIDEO123456','url':'https://www.youtube.com/watch?v=VIDEO123456','channel':store.value['channel'],'privacy':plan['privacy']}
 qt=Q.QApplication([]);main=app.Window();assert not hasattr(main,'upload_after')
 source=Path(td)/'Family_Full_SBS_test.mp4';source.write_bytes(b'test')
 def wait(dialog):
  for _ in range(400):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy():qt.processEvents();return
  raise AssertionError('Worker stuck')
 with patch.object(d,'YouTubeClient',Client):
  dialog=d.YouTubeDialog(main,str(source),title='Family trip');dialog.show();qt.processEvents()
  assert not calls and dialog.privacy.currentData()=='private' and dialog.kids.currentData() is None and 'Family trip' in dialog.description.toPlainText()
  dialog.submit();assert dialog.plan is None and 'made for kids' in dialog.status.text() and not calls
  dialog.kids.setCurrentIndex(1);dialog.synthetic.setChecked(True);dialog.privacy.setCurrentIndex(1)
  plan=dialog.reviewed_plan();assert plan['privacy']=='unlisted' and plan['channel_id']=='channel-one' and not calls
  dialog.template.setPlainText('Made with Stereo Slideshow. {title}');dialog.tags.setText('3D, Family');dialog.save_defaults()
  with patch.object(d,'prepare_stereo',lambda *args:source):dialog.submit();wait(dialog)
  assert len(calls)==1 and dialog.uploaded and dialog.result_url.endswith('VIDEO123456') and not dialog.go.isEnabled() and dialog.open_video.isVisible()
  dialog.reject()
  again=d.YouTubeDialog(main);assert again.privacy.currentData()=='private' and again.template.toPlainText()=='Made with Stereo Slideshow. {title}';again.reject()
  # Completion and failure never start uploads; previews never become upload defaults.
  main.actual_output=td
  with patch.object(app.QtGui.QDesktopServices,'openUrl',return_value=True):main.finished([str(source)])
  assert len(calls)==1 and main.last_exports==[str(source)] and main.watch.isEnabled()
  main.error('Cancelled.');assert len(calls)==1
  seen=[]
  with patch.object(d.YouTubeDialog,'exec',lambda obj:seen.append(obj.file.text())):main.upload_youtube()
  assert seen==[str(source)] and len(calls)==1
  slow=d.YouTubeDialog(main,str(source));slow.show()
  def action(w):w.cancel.wait(2);raise y.UploadCancelled()
  slow.start_job(action,lambda x:None);slow.reject();assert slow.isVisible();wait(slow);assert 'Cancelled' in slow.status.text();slow.reject()
 main.project_dirty=False;main.close();qt.processEvents()
 print('YouTube UI: explicit manual upload only, channel/audience/visibility review, reusable template, finished-video default, no upload on render completion/failure, result link and safe cancellation passed.')
