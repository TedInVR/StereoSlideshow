"""Modal export keeps source editing and application shutdown out of an active copy."""
import threading
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets as Q
from engine import Cancelled
from resolve_export import export_timeline

class ExportWorker(QtCore.QThread):
    progress=QtCore.Signal(int,int,str);done=QtCore.Signal(str);failed=QtCore.Signal(str)
    def __init__(self,parent,folder,snapshot,cfg):
        super().__init__(parent);self.folder=folder;self.snapshot=snapshot;self.cfg=cfg;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit(export_timeline(self.folder,self.snapshot,self.cfg,self.cancel,self.progress.emit))
        except Cancelled:self.failed.emit('Export cancelled. No finished export was replaced.')
        except Exception as e:self.failed.emit('Could not export: '+str(e)[:400])

class ResolveDialog(Q.QDialog):
    def __init__(self,parent,snapshot,cfg):
        super().__init__(parent);self.setWindowTitle('Export editable timeline for DaVinci Resolve');self.resize(620,380)
        self.snapshot=snapshot;self.cfg=cfg;self.worker=None;self.result_folder=''
        layout=Q.QVBoxLayout(self)
        text=Q.QLabel('Create a portable timeline with individual photos and video clips, separate music, and enabled clip sound. Requires Resolve 18.5 or newer.\n\nThis first-stage export uses original source media. Stereo eye framing and the app’s animation, backgrounds, titles, captions and fades need to be set up in Resolve. A caption cue sheet and instructions are included.');text.setWordWrap(True);layout.addWidget(text)
        layout.addWidget(Q.QLabel('Parent folder for a new Resolve Export folder:'))
        self.folder=Q.QLineEdit(str(Path(snapshot['media'][0]['path']).parent));layout.addWidget(self.folder)
        self.browse=Q.QPushButton('Choose folder…');self.browse.clicked.connect(self.choose);layout.addWidget(self.browse)
        self.status=Q.QLabel('Your original media and saved project remain unchanged.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.bar=Q.QProgressBar();self.bar.hide();layout.addWidget(self.bar)
        row=Q.QHBoxLayout();layout.addLayout(row)
        self.start=Q.QPushButton('Export editable timeline');self.start.clicked.connect(self.begin);row.addWidget(self.start)
        self.open=Q.QPushButton('Open export folder');self.open.setEnabled(False);self.open.clicked.connect(lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.result_folder)));row.addWidget(self.open)
        self.close_button=Q.QPushButton('Close');self.close_button.clicked.connect(self.reject);row.addWidget(self.close_button)
    def choose(self):
        value=Q.QFileDialog.getExistingDirectory(self,'Choose export parent folder',self.folder.text())
        if value:self.folder.setText(value)
    def begin(self):
        if not self.folder.text().strip():self.status.setText('Choose a destination folder first.');return
        self.worker=ExportWorker(self,self.folder.text(),self.snapshot,self.cfg)
        self.parent().project_worker=self.worker
        self.worker.progress.connect(self.progress);self.worker.done.connect(self.done_export);self.worker.failed.connect(self.status.setText);self.worker.finished.connect(self.finished_export)
        for control in [self.start,self.folder,self.browse,self.open]:control.setEnabled(False)
        self.close_button.setText('Cancel');self.bar.show();self.worker.start()
    def progress(self,current,total,text):
        self.bar.setRange(0,total);self.bar.setValue(current);self.status.setText(text)
    def done_export(self,folder):
        self.result_folder=folder;self.status.setText('Ready. In Resolve choose File > Import > Timeline and select Edit in Resolve.otioz. Read the included instructions for stereo framing and effects.');self.open.setEnabled(True)
    def finished_export(self):
        if self.parent().project_worker is self.worker:self.parent().project_worker=None
        self.close_button.setText('Close');self.bar.hide()
        for control in [self.start,self.folder,self.browse]:control.setEnabled(True)
    def reject(self):
        if self.worker and self.worker.isRunning():self.worker.cancel.set();self.status.setText('Cancelling…');return
        super().reject()
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():self.reject();event.ignore()
        else:event.accept()
