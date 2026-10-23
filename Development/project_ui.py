"""File-menu project snapshots and background media copying."""
import json,math,threading
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets as Q
from app_paths import VERSION,ROOT
from engine import VIDEO_EXT
from organizer import audio_item
from project_bundle import EXT,ProjectCancelled,ProjectError,read_project,save_project,new_project_path

CONTROLS=['title','sec','end_mode','fit_music','animation','drift','closing','pause','title_sec','motion','res','aspect','backdrop','layers','layer_strength','cross','video_half','video_cross','video_sound','sbs','ana','yt','out','source']
class ProjectWorker(QtCore.QThread):
    progress=QtCore.Signal(int,int,str);done=QtCore.Signal(str);failed=QtCore.Signal(str)
    def __init__(self,path,snapshot,parent):
        super().__init__(parent);self.path=path;self.snapshot=snapshot;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit(save_project(self.path,self.snapshot,self.cancel,self.progress.emit))
        except ProjectCancelled:self.failed.emit('Project save cancelled. The previous saved project, if any, is unchanged.')
        except Exception as error:self.failed.emit('Project could not be saved: '+str(error)[:450])

class ProjectMixin:
    def setup_projects(self,menu):
        try:generator=json.loads((ROOT/'Settings/music_generator.json').read_text())
        except (OSError,ValueError):generator={}
        self.project_music_style={key:generator[key] for key in ['era','genre','mood','details'] if isinstance(generator.get(key),str)}
        self.project_file=None;self.project_dirty=False;self.project_revision=0;self.project_worker=None;self._loading_project=False;self._after_save=None
        for label,callback in [('Save Project',self.save_project),('Save Project As…',self.save_project_as),('Open Project…',self.open_project)]:
            action=menu.addAction(label);action.triggered.connect(lambda _=False,fn=callback:fn())
        for name,callback in [('save_project',self.save_project),('save_project_as',self.save_project_as),('open_project',self.open_project)]:self.shortcuts.bind(self,name,callback)
        for name in CONTROLS:
            widget=getattr(self,name)
            if isinstance(widget,Q.QCheckBox):widget.toggled.connect(self.project_changed)
            elif isinstance(widget,Q.QComboBox):widget.currentIndexChanged.connect(self.project_changed)
            elif isinstance(widget,Q.QDoubleSpinBox):widget.valueChanged.connect(self.project_changed)
            else:widget.textChanged.connect(self.project_changed)
        for widget in [self.files,self.music_files]:
            for signal in [widget.model().rowsInserted,widget.model().rowsRemoved,widget.model().rowsMoved]:signal.connect(self.project_changed)
        self.files.itemChanged.connect(self.project_changed)
    def project_changed(self,*args):
        if self._loading_project:return
        self.project_revision+=1;self.project_dirty=True;self.project_window_title()
    def project_window_title(self):
        name=(' — '+self.project_file.stem+(' *' if self.project_dirty else '')) if self.project_file else ''
        self.setWindowTitle('Stereo Slideshow — v'+VERSION+name)
    def project_snapshot(self):
        settings={}
        for name in CONTROLS:
            widget=getattr(self,name)
            if isinstance(widget,Q.QCheckBox):value=widget.isChecked()
            elif isinstance(widget,Q.QComboBox):value=widget.currentIndex()
            elif isinstance(widget,Q.QDoubleSpinBox):value=widget.value()
            else:value=widget.text()
            settings[name]=value
        settings.update(music_style=self.project_music_style,bg=self.bg,fg=self.fg,caption_front=self.caption_front,manual_seconds=self.manual_seconds if self.fit_music.isChecked() else self.sec.value())
        media=[{'path':self.files.item(i).data(QtCore.Qt.UserRole),'sound':self.files.item(i).checkState()!=QtCore.Qt.Unchecked} for i in range(self.files.count())]
        captions={item['path']:self.captions.get(item['path'],Path(item['path']).stem) for item in media}
        return dict(settings=settings,media=media,music=self.playlist(),captions=captions)
    def project_busy(self):
        return (self.worker is not None and self.worker.isRunning()) or (self.project_worker is not None and self.project_worker.isRunning())
    def save_project(self):
        if self.project_busy():self.status.setText('Finish the current render or project save first.');return
        path=self.project_file
        if path is None:
            paths=[self.files.item(i).data(QtCore.Qt.UserRole) for i in range(self.files.count())]+self.playlist()
            parent=Path(paths[0]).parent if paths else Path.home()/'Documents'
            path=new_project_path(parent,self.title.text())
        self.save_project_to(path)
    def save_project_as(self):
        if self.project_busy():self.status.setText('Finish the current render or project save first.');return
        paths=[self.files.item(i).data(QtCore.Qt.UserRole) for i in range(self.files.count())]+self.playlist()
        parent=self.project_file.parent.parent if self.project_file else Path(paths[0]).parent if paths else Path.home()/'Documents'
        from output_names import safe_title
        choice,_=Q.QFileDialog.getSaveFileName(self,'Choose a name and location for the project folder',str(parent/((safe_title(self.title.text()) or 'Untitled')+EXT)),'Stereo Slideshow project (*'+EXT+')')
        if choice:self.save_project_to(new_project_path(Path(choice).parent,Path(choice).stem))
    def save_project_to(self,path):
        snapshot=self.project_snapshot();revision=self.project_revision
        self.project_worker=ProjectWorker(path,snapshot,self)
        dialog=Q.QProgressDialog('Preparing project media…','Cancel',0,max(1,len(snapshot['media'])+len(snapshot['music'])),self);dialog.setWindowTitle('Save Project');dialog.setWindowModality(QtCore.Qt.WindowModal);dialog.setMinimumDuration(0);dialog.setAutoClose(False);dialog.setAutoReset(False);dialog.canceled.connect(self.project_worker.cancel.set);self._save_dialog=dialog
        self.project_worker.progress.connect(lambda value,total,text:(dialog.setMaximum(max(1,total)),dialog.setValue(value),dialog.setLabelText(text)))
        self.project_worker.done.connect(lambda file:self._project_saved(file,revision));self.project_worker.failed.connect(self._project_failed);self.project_worker.finished.connect(self._project_save_finished)
        self.start.setEnabled(False);dialog.show();self.project_worker.start()
    def _project_saved(self,file,revision):
        self.project_file=Path(file);self.project_dirty=self.project_revision!=revision;self.project_window_title();self.status.setText('Project saved: '+file)
        self._project_save_ok=True
    def _project_failed(self,message):
        self._project_save_ok=False;self._after_save=None;self.status.setText(message)
    def _project_save_finished(self):
        self._save_dialog.close();self.start.setEnabled(True)
        action=self._after_save;self._after_save=None
        if action and getattr(self,'_project_save_ok',False) and not self.project_dirty:QtCore.QTimer.singleShot(0,action)
    def project_can_replace(self,continuation):
        if not self.project_file or not self.project_dirty:return True
        answer=Q.QMessageBox.question(self,'Unsaved project changes','Save changes to the current project first?',Q.QMessageBox.Save|Q.QMessageBox.Discard|Q.QMessageBox.Cancel,Q.QMessageBox.Save)
        if answer==Q.QMessageBox.Discard:return True
        if answer==Q.QMessageBox.Save:self._after_save=continuation;self.save_project()
        return False
    def validate_project_settings(self,settings):
        for name in CONTROLS:
            if name not in settings:raise ProjectError('The project is missing settings: '+name)
            widget=getattr(self,name);value=settings[name]
            if isinstance(widget,Q.QCheckBox):valid=isinstance(value,bool)
            elif isinstance(widget,Q.QComboBox):valid=isinstance(value,int) and not isinstance(value,bool) and 0<=value<widget.count()
            elif isinstance(widget,Q.QDoubleSpinBox):valid=isinstance(value,(int,float)) and math.isfinite(value) and widget.minimum()<=value<=widget.maximum()
            else:valid=isinstance(value,str)
            if not valid:raise ProjectError('The project setting is invalid: '+name)
        style=settings.get('music_style',{})
        if not isinstance(style,dict) or any(key not in ['era','genre','mood','details'] or not isinstance(value,str) for key,value in style.items()):raise ProjectError('The project music style is invalid.')
        for name in ['bg','fg']:
            if not isinstance(settings.get(name),str) or not QtGui.QColor(settings[name]).isValid():raise ProjectError('The project contains an invalid color.')
        if not isinstance(settings.get('caption_front'),bool):raise ProjectError('The project caption setting is invalid.')
        value=settings.get('manual_seconds')
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not self.sec.minimum()<=value<=self.sec.maximum():raise ProjectError('The manual photo duration is invalid.')
    def open_project(self,path=None):
        if self.project_busy():self.status.setText('Finish the current render or project save first.');return
        if not path:
            path,_=Q.QFileDialog.getOpenFileName(self,'Open Stereo Slideshow project',str(self.project_file.parent if self.project_file else Path.home()),'Stereo Slideshow project (*'+EXT+')')
        if not path:return
        try:data=read_project(path);self.validate_project_settings(data['settings'])
        except ProjectError as error:Q.QMessageBox.warning(self,'Cannot open project',str(error));return
        if not self.project_can_replace(lambda:self.open_project(path)):return
        self.restore_project(path,data)
    def restore_project(self,path,data):
        settings=data['settings'];self._loading_project=True
        blockers=[QtCore.QSignalBlocker(getattr(self,name)) for name in CONTROLS]
        try:
            for name in CONTROLS:
                widget=getattr(self,name);value=settings[name]
                if isinstance(widget,Q.QCheckBox):widget.setChecked(value)
                elif isinstance(widget,Q.QComboBox):widget.setCurrentIndex(value)
                elif isinstance(widget,Q.QDoubleSpinBox):widget.setValue(value)
                else:widget.setText(value)
            self.project_music_style=dict(settings.get('music_style',{}))
            self.bg=settings['bg'];self.fg=settings['fg'];self.bgbutton.setText(self.bg);self.fgbutton.setText(self.fg);self.caption_front=settings['caption_front'];self.manual_seconds=settings['manual_seconds'];self.captions=data['captions'];self.muted_paths=set()
            self.files.clear()
            for record in data['media']:
                source=record['resolved'];item=Q.QListWidgetItem(Path(source).name);item.setData(QtCore.Qt.UserRole,source);item.setToolTip(source)
                if Path(source).suffix.lower() in VIDEO_EXT:
                    item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable);item.setCheckState(QtCore.Qt.Checked if record.get('sound',True) else QtCore.Qt.Unchecked)
                    if not record.get('sound',True):self.muted_paths.add(source)
                self.files.addItem(item)
            self.set_playlist([record['resolved'] for record in data['music']])
            self.sec.setEnabled(not self.fit_music.isChecked());self.out.setEnabled(not self.source.isChecked());self.describe_animation()
            self.project_file=Path(path).resolve();self.project_dirty=False;self.project_revision+=1
        finally:
            del blockers;self._loading_project=False
        self.project_window_title();self.schedule_timing();self.status.setText('Project opened: '+str(self.project_file))
