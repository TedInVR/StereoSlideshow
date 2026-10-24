import os,sys,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
    os.environ['STEREO_SLIDESHOW_HOME']=td
    from PySide6 import QtWidgets as Q,QtTest
    import app,update_dialog as d,update_core as core
    from PIL import Image
    qt=Q.QApplication([]);main=app.Window();main.show()
    assert any(a.text()=='Check for Updates…' for a in main.menu.actions()[1].menu().actions())
    release=dict(sha='a'*40,version='99.0',available=True)
    job=Path(td)/'Updates/download-test';job.mkdir(parents=True);(job/'payload').mkdir()
    downloaded=dict(package=str(job/'payload'),job=str(job),version='99.0')
    def wait(dialog):
        for _ in range(600):
            qt.processEvents();QtTest.QTest.qWait(5)
            if dialog.worker and not dialog.busy():qt.processEvents();return
        raise AssertionError('Updater stuck')
    with patch.object(d,'check_update',lambda *args:release),patch.object(d,'stage_update',lambda *args:downloaded):
        dialog=d.UpdateDialog(main);dialog.show();wait(dialog);assert dialog.go.text()=='Download update'
        dialog.act();wait(dialog);assert dialog.go.text()=='Install and restart' and job.exists()
        assert main.isVisible() # check/download do not quit or install
        with patch.object(Q.QMessageBox,'question',return_value=Q.QMessageBox.Cancel):
            main.project_dirty=True;dialog.install();assert main.isVisible() and not dialog.installing
        calls=[]
        with patch.object(Q.QMessageBox,'question',return_value=Q.QMessageBox.Discard),patch.object(core,'launch_installer',lambda *args:calls.append(args)):
            dialog.install();qt.processEvents()
        assert len(calls)==1 and not main.isVisible()
        # Save is asynchronous: finish the portable project before handing off installation.
        main.show();photo=Path(td)/'Photo.jpg';Image.new('RGB',(100,50)).save(photo);main.add([str(photo)])
        saved_dialog=d.UpdateDialog(main);saved_dialog.show();wait(saved_dialog);saved_dialog.download=downloaded
        save_calls=[]
        with patch.object(Q.QMessageBox,'question',return_value=Q.QMessageBox.Save),patch.object(core,'launch_installer',lambda *args:save_calls.append(args)):
            saved_dialog.install()
            for _ in range(600):
                qt.processEvents();QtTest.QTest.qWait(5)
                if save_calls:break
        assert len(save_calls)==1 and main.project_file.is_file() and not main.isVisible()
    # Closing a downloaded update removes its staging files without touching settings.
    main.show();main.project_dirty=False
    with patch.object(d,'check_update',lambda *args:dict(release,available=False)):
        dialog=d.UpdateDialog(main);dialog.show();wait(dialog);assert 'up to date' in dialog.status.text()
        dialog.download=downloaded;dialog.reject();assert not job.exists()
    def slow(current,cancel):cancel.wait(3);raise core.UpdateCancelled()
    with patch.object(d,'check_update',slow):
        dialog=d.UpdateDialog(main);dialog.show();qt.processEvents();dialog.reject();assert dialog.isVisible();wait(dialog)
        assert 'cancelled' in dialog.status.text();dialog.reject()
    main.close();qt.processEvents()
print('Updater UI: Help menu, check/download/install separation, no automatic quit, unsaved-work Cancel, explicit restart handoff, up-to-date result and cancellation cleanup passed.')
