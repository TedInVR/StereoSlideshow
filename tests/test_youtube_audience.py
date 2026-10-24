import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=td
 from PySide6 import QtCore,QtWidgets as Q
 import youtube_dialog as d,youtube_audience as a
 qt=Q.QApplication([]);dialog=d.YouTubeDialog();dialog.show();qt.processEvents()
 assert dialog.kids.currentData() is None and 'could watch' in dialog.audience_hint.text() and 'choose No' in dialog.audience_hint.text()
 assert 'general audience' in dialog.kids.itemText(1) and 'directed at children' in dialog.kids.itemText(2)
 dialog.kids.setCurrentIndex(1);assert dialog.kids.currentData() is False and 'adults-only' in dialog.audience_hint.text()
 dialog.kids.setCurrentIndex(2);assert dialog.kids.currentData() is True and 'other ads may still run' in dialog.audience_hint.text()
 with patch.object(a,'show_audience_help') as help:
  # The signal's closure references the function imported when the dialog was built.
  other=d.YouTubeDialog();other.audience_help.click();help.assert_called_once_with(other);other.reject()
 original=dialog.kids.currentData()
 QtCore.QTimer.singleShot(20,lambda:qt.activeModalWidget().reject())
 a.show_audience_help(dialog);assert dialog.kids.currentData() is original
 assert 'primary audience' in a.DETAILS and 'contextual ads' in a.DETAILS and 'age restrictions are a separate issue' in a.DETAILS
 dialog.grab().save(str(Path(__file__).resolve().parents[3]/'build/youtube_audience_ui.png'));dialog.reject()
 print('Clear audience labels, neutral initial choice, conditional general-audience guidance, correct True/False mapping, contextual-ad/mixed-audience explanation and non-mutating help dialog passed.')
