"""Real preview renders remain separate from final output and upload state."""
import os,sys,json,tempfile,subprocess,wave
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
    os.environ['STEREO_SLIDESHOW_HOME']=td
    from PySide6 import QtWidgets as Q,QtTest
    from PIL import Image
    import app
    from engine import binary
    qt=Q.QApplication([]);main=app.Window()
    assert not hasattr(main,'upload_after') and not hasattr(main,'review_youtube_render')
    p=Path(td)/'Photo.jpg';Image.new('RGB',(200,100),'red').save(p);main.add([str(p)])
    main.title.setText('Preview test');main.sec.setValue(1);main.pause.setValue(0);main.title_sec.setValue(1);main.closing.setValue(1)
    music=Path(td)/'Music.wav'
    with wave.open(str(music),'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*8000)
    main.set_playlist([str(music)])
    saved=Path(td)/'Finished_Full_SBS_test.mp4';saved.write_bytes(b'keep final')
    main.last_exports=[str(saved)];main.watch.setEnabled(True)
    before=main.project_snapshot();settings=app.SETTINGS.read_bytes() if app.SETTINGS.exists() else None;opened=[]
    def wait():
        for _ in range(10000):
            qt.processEvents();QtTest.QTest.qWait(5)
            if not main.worker.isRunning():qt.processEvents();return
        status=main.status.text();main.cancel();main.worker.wait(3000);raise AssertionError('Render stuck: '+status)
    with patch.object(app.QtGui.QDesktopServices,'openUrl',lambda url:opened.append(url.toLocalFile()) or True):
        main.begin(preview=True);assert main.preview_job and not main.preview.isEnabled();wait()
        assert main.last_exports==[str(saved)] and saved.read_bytes()==b'keep final'
        assert main.project_snapshot()==before and main.preview.isEnabled() and not main.preview_job
        assert (app.SETTINGS.read_bytes() if app.SETTINGS.exists() else None)==settings
        assert opened and str(Path(opened[-1]).parent)==main.preview_temp.name
        probe=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-select_streams','v:0','-show_entries','stream=height,r_frame_rate:format=duration','-of','json',opened[-1]]))
        assert probe['streams'][0]['height']==270 and probe['streams'][0]['r_frame_rate']=='15/1'
        duration=float(probe['format']['duration']);assert duration==6
        audio=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-select_streams','a:0','-show_entries','stream=codec_name','-of','json',opened[-1]]));assert audio['streams'][0]['codec_name']=='aac'
        main.begin(preview=True,preview_anaglyph=True);wait()
        assert '_Anaglyph_' in opened[-1] and main.last_exports==[str(saved)]
        main.watch_finished();assert opened[-1]==str(saved)
        # Final completion enables review, never opens an upload dialog.
        main.actual_output=td
        with patch.object(app.Window,'upload_youtube',side_effect=AssertionError('Automatic upload')):main.finished([str(saved)])
        assert main.watch.isEnabled() and 'Watch finished' in main.status.text()
        main.begin(preview=True);main.cancel();wait();assert main.last_exports==[str(saved)] and main.preview.isEnabled()
    main.project_dirty=False;main.close();qt.processEvents()
    if main.preview_temp:main.preview_temp.cleanup()
print('Preview: actual SBS/anaglyph output at 270p/15 fps, correct duration, player launch, unchanged settings/final files, review-only completion and cancellation passed.')
