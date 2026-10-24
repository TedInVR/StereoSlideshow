import shutil,threading
from PySide6 import QtCore,QtWidgets as Q
from app_paths import ROOT,VERSION
from update_core import check_update,stage_update,UpdateCancelled

class UpdateWorker(QtCore.QThread):
    done=QtCore.Signal(object);failed=QtCore.Signal(str);progress=QtCore.Signal(int,int,str)
    def __init__(self,parent,action):super().__init__(parent);self.action=action;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit(self.action(self))
        except UpdateCancelled:self.failed.emit('Update cancelled. Your installed app is unchanged.')
        except Exception as error:self.failed.emit('Could not complete the update check or download: '+str(error)[:350]+'\nCheck your connection and try again. Your installed app is unchanged.')

class UpdateDialog(Q.QDialog):
    def __init__(self,parent):
        super().__init__(parent);self.setWindowTitle('Stereo Slideshow — Check for Updates');self.resize(540,300)
        self.worker=None;self.release=None;self.download=None;self.installing=False
        layout=Q.QVBoxLayout(self);layout.addWidget(Q.QLabel('Installed version: '+VERSION))
        self.status=Q.QLabel('Check for an update from the official TedInVR/StereoSlideshow GitHub project.');self.status.setWordWrap(True);self.status.setTextFormat(QtCore.Qt.PlainText);layout.addWidget(self.status)
        note=Q.QLabel('Downloads are handled inside the app folder and cleaned up automatically. Installation restarts the app and preserves your settings and existing icon. Finish other work before installing.');note.setWordWrap(True);layout.addWidget(note)
        self.bar=Q.QProgressBar();self.bar.hide();layout.addWidget(self.bar)
        row=Q.QHBoxLayout();layout.addLayout(row);self.go=Q.QPushButton('Check for updates');self.go.clicked.connect(self.act);row.addWidget(self.go)
        self.close_button=Q.QPushButton('Close');self.close_button.clicked.connect(self.reject);row.addWidget(self.close_button)
        if hasattr(parent,'shortcuts'):parent.shortcuts.bind(self,'close',self.reject)
        QtCore.QTimer.singleShot(0,self.act)
    def busy(self):return self.worker is not None and self.worker.isRunning()
    def start(self,action,callback):
        if self.busy():return
        self.go.setEnabled(False);self.close_button.setText('Cancel');self.bar.setRange(0,0);self.bar.show()
        self.worker=UpdateWorker(self,action);self.parent().project_worker=self.worker
        self.worker.done.connect(callback);self.worker.failed.connect(self.failed);self.worker.progress.connect(self.progress);self.worker.finished.connect(self.job_finished);self.worker.start()
    def act(self):
        if self.busy():return
        if self.download:self.install();return
        if self.release and self.release['available']:
            self.status.setText('Downloading version '+self.release['version']+'…')
            self.start(lambda w:stage_update(ROOT,self.release,w.cancel,w.progress.emit),self.ready)
        else:
            self.status.setText('Checking GitHub…');self.start(lambda w:check_update(VERSION,w.cancel),self.checked)
    def checked(self,release):
        self.release=release
        if release['available']:self.status.setText('Version '+release['version']+' is available.');self.go.setText('Download update')
        else:self.status.setText('You’re up to date. Installed version: '+VERSION+'.');self.go.setText('Check again')
    def ready(self,download):
        self.download=download;self.status.setText('Version '+download['version']+' is downloaded and verified. Install and restart when you are ready.');self.go.setText('Install and restart')
    def failed(self,message):self.status.setText(message)
    def job_finished(self):
        if self.parent().project_worker is self.worker:self.parent().project_worker=None
        self.go.setEnabled(True);self.bar.hide();self.close_button.setText('Close')
    def progress(self,current,total,text):
        self.status.setText(text);self.bar.setRange(0,100 if total else 0)
        if total:self.bar.setValue(min(100,round(current/total*100)))
    def install(self):
        parent=self.parent()
        if parent.project_busy():self.status.setText('Finish the current operation before installing.');return
        if parent.project_dirty:
            answer=Q.QMessageBox.question(self,'Save your project before updating?','Save your current slideshow project before restarting?',Q.QMessageBox.Save|Q.QMessageBox.Discard|Q.QMessageBox.Cancel,Q.QMessageBox.Save)
            if answer==Q.QMessageBox.Cancel:return
            if answer==Q.QMessageBox.Save:
                parent._after_save=self.install;parent.save_project();return
        self.installing=True;parent.pending_app_update=self.download;self.accept();parent.close()
        if parent.isVisible():parent.pending_app_update=None;self.installing=False;self.show();self.status.setText('The app could not close yet. Finish other operations and try Install and restart again.')
    def reject(self):
        if self.busy():self.worker.cancel.set();self.status.setText('Cancelling…');return
        if self.download and not self.installing:shutil.rmtree(self.download['job'],ignore_errors=True);self.download=None
        super().reject()
    def closeEvent(self,event):
        if self.busy():self.reject();event.ignore()
        else:self.reject();event.accept()
