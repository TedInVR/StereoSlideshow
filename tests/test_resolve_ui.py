import os,sys,tempfile,threading
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
    os.environ['STEREO_SLIDESHOW_HOME']=td
    from PySide6 import QtWidgets as Q,QtTest
    from PIL import Image
    import app,resolve_dialog as r
    from engine import Cancelled
    qt=Q.QApplication([]);main=app.Window()
    photo=Path(td)/'Test.jpg';Image.new('RGB',(100,50)).save(photo);main.add([str(photo)])
    def wait(d):
        for _ in range(500):
            qt.processEvents();QtTest.QTest.qWait(5)
            if not d.worker.isRunning():qt.processEvents();return
        raise AssertionError('Export worker stuck')
    d=r.ResolveDialog(main,main.project_snapshot(),main.timing_config());d.show();d.begin();assert main.project_busy();wait(d)
    assert d.open.isEnabled() and Path(d.result_folder,'Edit in Resolve.otioz').is_file();assert main.project_worker is None;d.reject()
    def slow(*args):args[3].wait(3);raise Cancelled()
    with patch.object(r,'export_timeline',slow):
        d=r.ResolveDialog(main,main.project_snapshot(),main.timing_config());d.show();d.begin();d.reject()
        assert d.isVisible() and d.worker.cancel.is_set();wait(d);assert 'cancelled' in d.status.text();d.reject()
    main.project_dirty=False;main.close();qt.processEvents()
print('Resolve UI: export action, source-folder default, background completion, render interlock and safe cancellation passed.')
