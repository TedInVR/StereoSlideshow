import os,sys,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
with tempfile.TemporaryDirectory() as td:
 os.environ['STEREO_SLIDESHOW_HOME']=str(Path(td)/'App')
 from PySide6 import QtCore,QtWidgets as Q,QtTest
 import app
 from project_bundle import read_project,new_project_path
 qt=Q.QApplication([]);main=app.Window();root=Path(td);photo=root/'Mom.jpg';clip=root/'Clip.mp4';song=root/'Tune.wav'
 for path in [photo,clip,song]:path.write_bytes(b'media')
 main.add([str(photo),str(clip),str(song)]);main.title.setText('Our trip');main.sec.setValue(11);main.aspect.setCurrentText('1:1');main.ana.setChecked(False);main.bg='#123456';main.caption_front=False;main.project_music_style={'era':'1950s','genre':'Ragtime'};main.captions={str(photo):'',str(clip):'A clip'}
 main.files.item(0).setCheckState(QtCore.Qt.Unchecked)
 path=new_project_path(root,'Our trip');main.save_project_to(path)
 for _ in range(400):
  qt.processEvents();QtTest.QTest.qWait(5)
  if not main.project_busy() and hasattr(main,'project_file') and main.project_file:break
 assert main.project_file==path and path.is_file() and not main.project_dirty
 main.title.setText('Changed');assert main.project_dirty
 with patch.object(Q.QMessageBox,'question',return_value=Q.QMessageBox.Discard):main.open_project(str(path))
 assert main.title.text()=='Our trip' and main.sec.value()==11 and main.aspect.currentText()=='1:1' and not main.ana.isChecked() and main.bg=='#123456' and not main.caption_front
 assert main.files.item(0).checkState()==QtCore.Qt.Unchecked
 restoredphoto=next(main.files.item(i).data(QtCore.Qt.UserRole) for i in range(main.files.count()) if main.files.item(i).text()=='Mom.jpg');assert main.captions[restoredphoto]=='' and all(str(path.parent) in p for p in main.playlist())
 assert not main.project_dirty and len(main.menu.actions())==2 and main.project_music_style['era']=='1950s' and main.project_music_style['genre']=='Ragtime' and main.project_music_style['music_mode']=='instrumental'
 main.title.setText('Edited')
 with patch.object(Q.QMessageBox,'question',return_value=Q.QMessageBox.Cancel):main.open_project(str(path))
 assert main.title.text()=='Edited'
 from project_bundle import save_project
 main.project_music_style.update(music_mode='lyrics',voice='Female lead',language='English',topic='Whalom Park',lyrics='[Verse]\nSummer memories',details='Warm piano and brass')
 vocalpath=new_project_path(root,'Vocal project');save_project(vocalpath,main.project_snapshot());main.project_music_style={};main.project_dirty=False;main.open_project(str(vocalpath))
 assert main.project_music_style['music_mode']=='lyrics' and main.project_music_style['voice']=='Female lead' and main.project_music_style['lyrics']=='[Verse]\nSummer memories' and main.project_music_style['details']=='Warm piano and brass'
 main.project_dirty=False;main.close();qt.processEvents()
 print('Project menu, async save, full UI restoration, portable media paths, blank captions, clip mute, dirty tracking and Cancel preservation passed.')
