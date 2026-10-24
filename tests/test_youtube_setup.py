"""The setup guide is resumable, never publishes, and keeps secrets off screen."""
import os,sys,json,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtWidgets as Q
 import youtube_setup as g,youtube_dialog as d
 from youtube_upload import atomic_json,SCOPES
 qt=Q.QApplication([]);guide=g.YouTubeSetup();guide.show();qt.processEvents();assert guide.currentId()==0 and len(guide.pageIds())==8
 guide.next();qt.processEvents();assert guide.currentId()==1 and not guide.button(Q.QWizard.NextButton).isEnabled()
 guide.project.setText('stereo-slideshow-demo');guide.pages[1].confirm.setChecked(True);guide.next();qt.processEvents();assert guide.currentId()==2
 with patch.object(g.QtGui.QDesktopServices,'openUrl',return_value=True) as browser:
  guide.open_google('auth/scopes');url=browser.call_args.args[0].toString();assert url=='https://console.cloud.google.com/auth/scopes?project=stereo-slideshow-demo'
 guide.copy('\n'.join(SCOPES));assert qt.clipboard().text()=='\n'.join(SCOPES)
 guide.reject();saved=json.loads(guide.progress_path.read_text());assert saved['step']==2 and '1' in saved['completed'] and 'client_secret' not in str(saved)
 resumed=g.YouTubeSetup();resumed.show();qt.processEvents();assert resumed.resume_step==2 and resumed.resume_button.isEnabled();resumed.reject();assert json.loads(guide.progress_path.read_text())['step']==2
 resumed=g.YouTubeSetup();resumed.show();qt.processEvents();resumed.resume_button.click();qt.processEvents();assert resumed.currentId()==2 and resumed.project.text()=='stereo-slideshow-demo'
 resumed.jump(7);qt.processEvents();resumed.accept();assert resumed.isVisible() and not resumed.needs_connect and 'First click' in resumed.file_error.text()
 wrong=Path(td)/'wrong.json';atomic_json(wrong,{'web':{'client_id':'wrong.apps.googleusercontent.com','client_secret':'SECRET'}})
 with patch.object(Q.QFileDialog,'getOpenFileName',return_value=(str(wrong),'')):resumed.pick_json()
 assert not resumed.config_file and 'Desktop' in resumed.file_error.text()
 good=Path(td)/'client_secret_example.json';atomic_json(good,{'installed':{'client_id':'example.apps.googleusercontent.com','client_secret':'NOT-A-REAL-SECRET'}})
 with patch.object(Q.QFileDialog,'getOpenFileName',return_value=(str(good),'')):resumed.pick_json()
 assert resumed.config_file==str(good) and 'NOT-A-REAL-SECRET' not in resumed.file_label.text()
 resumed.grab().save(str(Path(__file__).resolve().parents[3]/'build/youtube_setup_wizard.png'));resumed.accept();assert resumed.result()==Q.QDialog.Accepted and resumed.needs_connect
 # A new install's Connect opens the walkthrough, rather than a dead-end error.
 dialog=d.YouTubeDialog()
 with patch.object(dialog,'setup_guide') as setup:dialog.connect_account();setup.assert_called_once()
 class AcceptedGuide:
  config_file=str(good);needs_connect=True
  def __init__(self,*args,**kwargs):pass
  def exec(self):return Q.QDialog.Accepted
 with patch.object(g,'YouTubeSetup',AcceptedGuide),patch.object(dialog,'connect_account') as connect:dialog.setup_guide();connect.assert_called_once()
 stored=json.loads(dialog.config_path.read_text());assert stored['installed']['client_id']=='example.apps.googleusercontent.com'
 connected=g.YouTubeSetup(connected=True);connected.jump(7);connected.show();qt.processEvents();connected.accept();assert connected.result()==Q.QDialog.Accepted and not connected.needs_connect
 dialog.reject();qt.processEvents()
 print('Eight setup steps, completion guidance, resume/close/back, project links, copyable scopes, Desktop JSON validation, secret-free progress/display, Connect fallback and final connection handoff passed. No Google access or upload performed.')
