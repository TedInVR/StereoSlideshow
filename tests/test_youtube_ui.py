import os,sys,json,tempfile,threading,copy
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtWidgets as Q,QtTest
 import app,youtube_dialog as d,youtube_upload as y
 class Store:
  value=dict(channel={'id':'channel-one','title':'Ted in VR'})
  def load(self):return copy.deepcopy(self.value)
  def save(self,x):self.value=x
  def delete(self):self.value=None
 store=Store()
 class Client:
  def __init__(self):self.store=store
  def upload(self,path,plan,cancel,status,progress):return {'id':'VIDEO123456','url':'https://www.youtube.com/watch?v=VIDEO123456','channel':store.value['channel'],'privacy':plan['privacy']}
 qt=Q.QApplication([]);main=app.Window();assert not main.upload_after.isChecked()
 def wait(dialog):
  for _ in range(400):
   qt.processEvents();QtTest.QTest.qWait(5)
   if not dialog.busy():qt.processEvents();return
  raise AssertionError('Worker stuck')
 with patch.object(d,'YouTubeClient',Client):
  dialog=d.YouTubeDialog(main,title='Family trip',arm=True);dialog.show();qt.processEvents()
  assert dialog.privacy.currentData()=='private' and dialog.kids.currentData() is None and 'Family trip' in dialog.description.toPlainText()
  dialog.submit();assert dialog.plan is None and 'made for kids' in dialog.status.text()
  dialog.kids.setCurrentIndex(1);dialog.synthetic.setChecked(True);dialog.privacy.setCurrentIndex(1);dialog.submit();assert dialog.result()==Q.QDialog.Accepted and dialog.plan['privacy']=='unlisted' and dialog.plan['channel_id']=='channel-one'
  plan=dict(dialog.plan);dialog.template.setPlainText('Made with Stereo Slideshow. {title}');dialog.tags.setText('3D, Family');dialog.save_defaults()
  source=Path(td)/'Family_Full_SBS_test.mp4';source.write_bytes(b'test')
  actual=d.YouTubeDialog(main,str(source),plan=plan);actual.show();qt.processEvents();assert actual.plan==plan
  with patch.object(d,'prepare_stereo',lambda *args:source):actual.start_armed();wait(actual)
  assert actual.uploaded and actual.result_url.endswith('VIDEO123456') and not actual.go.isEnabled() and actual.open_video.isVisible()
  actual.grab().save(str(Path(__file__).resolve().parents[3]/'build/youtube_upload_dialog.png'));actual.reject()
  again=d.YouTubeDialog(main);assert again.privacy.currentData()=='private' and again.template.toPlainText()=='Made with Stereo Slideshow. {title}';again.reject()
  # Auto-upload uses exactly the reviewed plan, once, only after success.
  main.pending_upload=plan;main.actual_output=td;seen=[]
  with patch.object(main,'upload_rendered_youtube',lambda source,approved:seen.append((source,approved))),patch.object(app.QtGui.QDesktopServices,'openUrl',return_value=True):main.finished([str(source)])
  assert seen==[(str(source),plan)] and main.pending_upload is None
  main.pending_upload=plan;main.error('Cancelled.');assert main.pending_upload is None
  # Closing a running dialog cancels without destroying its thread.
  slow=d.YouTubeDialog(main,str(source));slow.show()
  def action(w):w.cancel.wait(2);raise y.UploadCancelled()
  slow.start_job(action,lambda x:None);slow.reject();assert slow.isVisible();wait(slow);assert 'Cancelled' in slow.status.text();slow.reject()
 main.project_dirty=False;main.close();qt.processEvents()
 print('YouTube UI: channel display, explicit audience/visibility, reusable template, armed plan, single automatic upload after success, failure clearing, result link and safe cancellation passed.')
