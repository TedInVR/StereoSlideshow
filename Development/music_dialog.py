"""In-app music choices, generation progress and preview."""
import json, threading, uuid
from pathlib import Path
from PySide6 import QtCore, QtWidgets as Q
from app_paths import ROOT
from music_generator import ERAS,GENRES,MOODS,MusicCancelled,generate_soundtrack,find_installation
from timing import format_time

class MusicWorker(QtCore.QThread):
    message=QtCore.Signal(str);done=QtCore.Signal(str);failed=QtCore.Signal(str)
    def __init__(self,options,seconds,output,parent):
        super().__init__(parent);self.options=options;self.seconds=seconds;self.output=output;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit(generate_soundtrack(self.options,self.seconds,self.output,self.cancel,self.message.emit))
        except MusicCancelled:self.failed.emit('Cancelled. If ACE-Step was already running separately, it may finish its current task in the background.')
        except Exception as error:self.failed.emit(str(error)[:600])

class MusicDialog(Q.QDialog):
    def __init__(self,seconds,parent=None):
        super().__init__(parent);self.setWindowTitle('Create music for this slideshow');self.resize(680,680);self.seconds=seconds;self.worker=None;self.result_path='';self.player=None
        self.settings_path=ROOT/'Settings/music_generator.json'
        try:saved=json.loads(self.settings_path.read_text())
        except (OSError,ValueError):saved={}
        outer=Q.QVBoxLayout(self);scroll=Q.QScrollArea();scroll.setWidgetResizable(True);panel=Q.QWidget();layout=Q.QVBoxLayout(panel);scroll.setWidget(panel);outer.addWidget(scroll,1)
        title=Q.QLabel('Create an original instrumental soundtrack');title.setStyleSheet('font-size:18px;font-weight:600');title.setWordWrap(True);layout.addWidget(title)
        label=Q.QLabel('Length: '+format_time(seconds)+'\nIncludes all photos and full video clips, the opening, closing fade and final black screen.');label.setWordWrap(True);layout.addWidget(label)
        note=Q.QLabel('Choose a style, generate, then listen before using it. Each generation requests a fresh random result. Era and genre are creative directions; results can vary.');note.setWordWrap(True);layout.addWidget(note)
        self.choices=Q.QWidget();form=Q.QFormLayout(self.choices);layout.addWidget(self.choices)
        for name,items,label in [('era',ERAS,'Era'),('genre',GENRES,'Genre'),('mood',MOODS,'Mood')]:
            widget=Q.QComboBox();widget.addItems(items);widget.setEditable(True);widget.setCurrentText(saved.get(name,items[0]));setattr(self,name,widget);form.addRow(label,widget)
        self.details=Q.QPlainTextEdit(saved.get('details',''));self.details.setPlaceholderText('Optional: piano and strings, a playful melody, no heavy drums…');self.details.setMaximumHeight(85);form.addRow('Your description',self.details)
        setup=Q.QGroupBox('Generator setup — ACE-Step 1.5 on this Mac');setup_form=Q.QFormLayout(setup);layout.addWidget(setup)
        self.folder=Q.QLineEdit(saved.get('folder') or find_installation());row=Q.QHBoxLayout();row.addWidget(self.folder);button=Q.QPushButton('Choose folder…');button.clicked.connect(self.pick_folder);row.addWidget(button);setup_form.addRow('ACE-Step folder',row)
        self.url=Q.QLineEdit(saved.get('url','http://127.0.0.1:8001'));setup_form.addRow('Local API address',self.url)
        self.token=Q.QLineEdit(saved.get('token',''));self.token.setEchoMode(Q.QLineEdit.Password);setup_form.addRow('API key (usually blank)',self.token)
        help=Q.QLabel('Choose the installed ACE-Step project folder once. The app starts its API engine as needed and stops the engine it started when generation finishes. An already-running local API can also be used. The browser interface on port 7860 is a different service.');help.setWordWrap(True);setup_form.addRow(help);self.setup=setup
        if seconds>600:
            note=Q.QLabel('This slideshow is longer than one generation. Matching sections will be created and crossfaded into one soundtrack.');note.setWordWrap(True);layout.addWidget(note)
        note=Q.QLabel('Using this result replaces the music playlist and keeps the photo timing shown here. Auto-Fit is turned off so the music follows your slideshow. Earlier music files are kept.');note.setWordWrap(True);layout.addWidget(note)
        self.status=Q.QLabel('Ready. First model loading can take several minutes.');self.status.setTextFormat(QtCore.Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.progress=Q.QProgressBar();self.progress.setRange(0,0);self.progress.hide();layout.addWidget(self.progress)
        row=Q.QHBoxLayout();layout.addLayout(row);self.generate=Q.QPushButton('Generate music');self.generate.clicked.connect(self.begin);row.addWidget(self.generate);self.cancel_button=Q.QPushButton('Cancel generation');self.cancel_button.clicked.connect(self.cancel_generation);self.cancel_button.setEnabled(False);row.addWidget(self.cancel_button)
        row=Q.QHBoxLayout();layout.addLayout(row);self.play=Q.QPushButton('Play preview');self.play.clicked.connect(self.preview);self.play.setEnabled(False);row.addWidget(self.play);self.stop=Q.QPushButton('Stop preview');self.stop.clicked.connect(self.stop_preview);self.stop.setEnabled(False);row.addWidget(self.stop)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Cancel);self.use=buttons.addButton('Use this music',Q.QDialogButtonBox.AcceptRole);self.use.setEnabled(False);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        from ui_controls import protect_settings_wheel
        protect_settings_wheel(self)
        if parent and hasattr(parent,'shortcuts'):parent.shortcuts.bind(self,'close',self.reject)
    def pick_folder(self):
        folder=Q.QFileDialog.getExistingDirectory(self,'Choose the ACE-Step project folder',self.folder.text() or str(Path.home()))
        if folder:self.folder.setText(folder)
    def begin(self):
        if self.worker and self.worker.isRunning():return
        self.stop_preview();options=dict(era=self.era.currentText(),genre=self.genre.currentText(),mood=self.mood.currentText(),details=self.details.toPlainText(),folder=self.folder.text().strip(),url=self.url.text().strip(),token=self.token.text(),logs=str(ROOT/'Logs'))
        try:
            from music_generator import local_url
            local_url(options['url']);self.settings_path.parent.mkdir(parents=True,exist_ok=True);self.settings_path.write_text(json.dumps({k:v for k,v in options.items() if k!='logs'},indent=2))
        except Exception as error:self.status.setText(str(error)[:400]);return
        # Keep every auditioned result: regenerating never overwrites an earlier take.
        output=ROOT/'Generated Music'/('Slideshow Music '+uuid.uuid4().hex[:12]+'.wav')
        self.worker=MusicWorker(options,self.seconds,output,self);self.worker.message.connect(self.status.setText);self.worker.done.connect(self.generated);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.idle)
        self.choices.setEnabled(False);self.setup.setEnabled(False);self.generate.setEnabled(False);self.use.setEnabled(False);self.play.setEnabled(False);self.cancel_button.setEnabled(True);self.progress.show();self.status.setText('Connecting to the local music engine…');self.worker.start()
    def generated(self,path):
        self.result_path=path;self.status.setText('Ready: '+Path(path).name+' — '+format_time(self.seconds)+'. Preview it, generate another take, or use this music.')
    def failed(self,message):self.status.setText(message)
    def idle(self):
        self.progress.hide();self.cancel_button.setEnabled(False);self.generate.setEnabled(True);self.generate.setText('Generate another take' if self.result_path else 'Generate music');self.choices.setEnabled(True);self.setup.setEnabled(True);self.use.setEnabled(bool(self.result_path));self.play.setEnabled(bool(self.result_path))
    def preview(self):
        if not self.result_path:return
        try:
            if self.player is None:
                from PySide6.QtMultimedia import QAudioOutput,QMediaPlayer
                self.audio=QAudioOutput(self);self.player=QMediaPlayer(self);self.player.setAudioOutput(self.audio);self.player.errorOccurred.connect(lambda *args:self.status.setText('Preview: '+self.player.errorString()));self.audio.setVolume(.7)
            self.player.setSource(QtCore.QUrl.fromLocalFile(self.result_path));self.player.play();self.stop.setEnabled(True)
        except Exception as error:self.status.setText('Preview unavailable: '+str(error)[:250])
    def stop_preview(self):
        if self.player:self.player.stop()
        if hasattr(self,'stop'):self.stop.setEnabled(False)
    def cancel_generation(self):
        if self.worker and self.worker.isRunning():self.worker.cancel.set();self.cancel_button.setEnabled(False);self.status.setText('Cancelling…')
    def busy(self):return self.worker is not None and self.worker.isRunning()
    def reject(self):
        if self.busy():self.cancel_generation();return
        self.stop_preview();super().reject()
    def accept(self):
        if self.busy() or not self.result_path:return
        self.stop_preview();super().accept()
    def closeEvent(self,event):
        if self.busy():self.cancel_generation();event.ignore()
        else:self.stop_preview();event.accept()
