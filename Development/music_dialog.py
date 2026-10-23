"""In-app music choices, generation progress and preview."""
import json, threading, uuid
from pathlib import Path
from PySide6 import QtCore, QtWidgets as Q
from app_paths import ROOT
from music_generator import ERAS,GENRES,MOODS,MusicCancelled,generate_soundtrack,find_installation,STYLE_KEYS,VOICES,LANGUAGES,validate_music_options
from timing import format_time
from audio_workbench import OPERATIONS,INSTRUMENTS,list_takes,metadata_for,take_style,import_take,export_take,edit_soundtrack,validate_edit
from engine import music_duration

class MusicWorker(QtCore.QThread):
    message=QtCore.Signal(str);done=QtCore.Signal(str);failed=QtCore.Signal(str)
    def __init__(self,options,seconds,output,parent):
        super().__init__(parent);self.options=options;self.seconds=seconds;self.output=output;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit((generate_soundtrack if self.options.get("operation","new")=="new" else edit_soundtrack)(self.options,self.seconds,self.output,self.cancel,self.message.emit))
        except MusicCancelled:self.failed.emit('Cancelled. If ACE-Step was already running separately, it may finish its current task in the background.')
        except Exception as error:self.failed.emit(str(error)[:600])

class AudioFileWorker(QtCore.QThread):
    done=QtCore.Signal(str);failed=QtCore.Signal(str)
    def __init__(self,action,parent):
        super().__init__(parent);self.action=action;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit(self.action(self.cancel))
        except MusicCancelled:self.failed.emit('Cancelled. Your original audio is unchanged.')
        except Exception as error:self.failed.emit(str(error)[:600])

class MusicDialog(Q.QDialog):
    def __init__(self,seconds,parent=None):
        super().__init__(parent);self.setWindowTitle('Create music for this slideshow');self.resize(680,680);self.seconds=seconds;self.worker=None;self.result_path='';self.source_path='';self.source_seconds=0.;self.player=None
        self.settings_path=ROOT/'Settings/music_generator.json'
        try:saved=json.loads(self.settings_path.read_text())
        except (OSError,ValueError):saved={}
        self.style_owner=parent if hasattr(parent,'project_music_style') else getattr(parent,'main',parent)
        saved.update(getattr(self.style_owner,'project_music_style',{}))
        outer=Q.QVBoxLayout(self);scroll=Q.QScrollArea();scroll.setWidgetResizable(True);panel=Q.QWidget();layout=Q.QVBoxLayout(panel);scroll.setWidget(panel);outer.addWidget(scroll,1)
        title=Q.QLabel('Create or edit your soundtrack');title.setStyleSheet('font-size:18px;font-weight:600');title.setWordWrap(True);layout.addWidget(title)
        label=Q.QLabel('Length: '+format_time(seconds)+'\nIncludes all photos and full video clips, the opening, closing fade and final black screen.');label.setWordWrap(True);layout.addWidget(label)
        note=Q.QLabel('Create a fresh take, or load existing audio to edit it. Listen before using a result. Every result is saved separately. Style directions and AI results can vary.');note.setWordWrap(True);layout.addWidget(note)
        self.library_box=Q.QGroupBox('Audio takes — keep, reload and edit');take_form=Q.QFormLayout(self.library_box);layout.addWidget(self.library_box)
        row=Q.QHBoxLayout();self.takes=Q.QComboBox();self.takes.setMinimumContentsLength(18);self.takes.setSizeAdjustPolicy(Q.QComboBox.AdjustToMinimumContentsLengthWithIcon);self.takes.setSizePolicy(Q.QSizePolicy.Ignored,Q.QSizePolicy.Fixed);row.addWidget(self.takes,1)
        self.load_take_button=Q.QPushButton('Load take');self.load_take_button.clicked.connect(self.load_selected_take);row.addWidget(self.load_take_button);take_form.addRow('Saved takes',row)
        row=Q.QHBoxLayout();self.import_button=Q.QPushButton('Import / reload audio…');self.import_button.clicked.connect(self.import_audio);row.addWidget(self.import_button)
        self.save_audio_button=Q.QPushButton('Save Audio As…');self.save_audio_button.clicked.connect(self.save_audio);self.save_audio_button.setEnabled(False);row.addWidget(self.save_audio_button);take_form.addRow(row)
        self.source_label=Q.QLabel('Source: no audio loaded');self.source_label.setWordWrap(True);self.source_label.setTextFormat(QtCore.Qt.PlainText);take_form.addRow(self.source_label)
        self.use_source_button=Q.QPushButton('Use previewed result as editing source');self.use_source_button.clicked.connect(self.use_result_source);self.use_source_button.setEnabled(False);take_form.addRow(self.use_source_button)
        note=Q.QLabel('Every take is kept automatically. Save Audio As exports WAV, FLAC or MP3 plus a companion JSON containing lyrics and settings. Keep both files together to reload those settings. Imports are copied; the original stays unchanged.');note.setWordWrap(True);take_form.addRow(note)
        self.operation=Q.QComboBox()
        for label,value in OPERATIONS:self.operation.addItem(label,value)
        take_form.addRow('What to do',self.operation)
        self.edit_box=Q.QWidget();edit_form=Q.QFormLayout(self.edit_box);edit_form.setContentsMargins(0,0,0,0);take_form.addRow(self.edit_box)
        self.edit_start=Q.QDoubleSpinBox();self.edit_end=Q.QDoubleSpinBox()
        for widget in (self.edit_start,self.edit_end):widget.setRange(0,86400);widget.setDecimals(2);widget.setSuffix(' s')
        self.range_label=Q.QLabel('Replace passage');self.range_widget=Q.QWidget();range_row=Q.QHBoxLayout(self.range_widget);range_row.setContentsMargins(0,0,0,0);range_row.addWidget(self.edit_start);range_row.addWidget(Q.QLabel('through'));range_row.addWidget(self.edit_end);edit_form.addRow(self.range_label,self.range_widget)
        self.instrument=Q.QComboBox();self.instrument.addItems(INSTRUMENTS);self.instrument_label=Q.QLabel('New instrument');edit_form.addRow(self.instrument_label,self.instrument)
        self.layer_volume=Q.QSpinBox();self.layer_volume.setRange(0,100);self.layer_volume.setValue(35);self.layer_volume.setSuffix(' %');self.layer_label=Q.QLabel('New instrument volume');edit_form.addRow(self.layer_label,self.layer_volume)
        self.edit_hint=Q.QLabel();self.edit_hint.setWordWrap(True);take_form.addRow(self.edit_hint)
        self.choices=Q.QWidget();form=Q.QFormLayout(self.choices);layout.addWidget(self.choices)
        self.mode=Q.QComboBox()
        for label,value in [('Instrumental','instrumental'),('Write a song about a topic','topic'),('Use my lyrics','lyrics')]:self.mode.addItem(label,value)
        self.mode.setCurrentIndex(max(0,self.mode.findData(saved.get('music_mode','instrumental'))));form.addRow('Music mode',self.mode)
        self.mode_hint=Q.QLabel();self.mode_hint.setWordWrap(True);form.addRow(self.mode_hint)
        for name,items,label in [('era',ERAS,'Era'),('genre',GENRES,'Genre'),('mood',MOODS,'Mood')]:
            widget=Q.QComboBox();widget.addItems(items);widget.setEditable(True);widget.setCurrentText(saved.get(name,items[0]));setattr(self,name,widget);form.addRow(label,widget)
        from description_presets import DescriptionPresets
        self.description_presets=DescriptionPresets(ROOT/'Settings/music_descriptions.json')
        row=Q.QHBoxLayout();self.saved_descriptions=Q.QComboBox();self.saved_descriptions.setSizeAdjustPolicy(Q.QComboBox.AdjustToMinimumContentsLengthWithIcon);self.saved_descriptions.setMinimumContentsLength(16);self.saved_descriptions.setSizePolicy(Q.QSizePolicy.Ignored,Q.QSizePolicy.Fixed);self.saved_descriptions.activated.connect(self.load_description);row.addWidget(self.saved_descriptions,1)
        self.save_description_button=Q.QPushButton('Save description…');self.save_description_button.clicked.connect(self.save_description);row.addWidget(self.save_description_button)
        self.remove_description_button=Q.QPushButton('Remove');self.remove_description_button.clicked.connect(self.remove_description);row.addWidget(self.remove_description_button);form.addRow('Saved descriptions',row)
        self.details=Q.QPlainTextEdit(saved.get('details',''));self.details.setPlaceholderText('Optional: piano and strings, a playful melody, no heavy drums…');self.details.setMinimumHeight(110);self.details.setMaximumHeight(160);form.addRow('Your description',self.details)
        self.vocal_panel=Q.QWidget();vocal_form=Q.QFormLayout(self.vocal_panel);vocal_form.setContentsMargins(0,0,0,0);form.addRow(self.vocal_panel)
        self.voice=Q.QComboBox();self.voice.addItems(VOICES);self.voice.setCurrentText(saved.get('voice','No preference'));vocal_form.addRow('Vocal preference',self.voice)
        self.language=Q.QComboBox();self.language.addItems(list(LANGUAGES));self.language.setCurrentText(saved.get('language','English'));vocal_form.addRow('Song language',self.language)
        self.topic=Q.QPlainTextEdit(saved.get('topic',''));self.topic.setPlaceholderText('For example: childhood summers at Whalom Park with family and friends.');self.topic.setFixedHeight(90);self.topic_label=Q.QLabel('Song topic');vocal_form.addRow(self.topic_label,self.topic)
        self.lyrics=Q.QPlainTextEdit(saved.get('lyrics',''));self.lyrics.setPlaceholderText('[Verse 1]\nYour words here…\n\n[Chorus]\nYour chorus…');self.lyrics.setMinimumHeight(180);self.lyrics.setMaximumHeight(240);self.lyrics_label=Q.QLabel('Lyrics');vocal_form.addRow(self.lyrics_label,self.lyrics)
        self.edit_generated=Q.QPushButton('Edit and use these lyrics for another take');self.edit_generated.clicked.connect(lambda:self.mode.setCurrentIndex(2));vocal_form.addRow(self.edit_generated)
        setup=Q.QGroupBox('Generator setup — ACE-Step 1.5 on this Mac');setup_form=Q.QFormLayout(setup);layout.addWidget(setup)
        self.folder=Q.QLineEdit(saved.get('folder') or find_installation());row=Q.QHBoxLayout();row.addWidget(self.folder);button=Q.QPushButton('Choose folder…');button.clicked.connect(self.pick_folder);row.addWidget(button);setup_form.addRow('ACE-Step folder',row)
        self.url=Q.QLineEdit(saved.get('url','http://127.0.0.1:8001'));setup_form.addRow('Local API address',self.url)
        self.token=Q.QLineEdit(saved.get('token',''));self.token.setEchoMode(Q.QLineEdit.Password);setup_form.addRow('API key (usually blank)',self.token)
        help=Q.QLabel('Choose the installed ACE-Step project folder once. The app starts its API engine as needed and stops the engine it started when generation finishes. An already-running local API can also be used. The browser interface on port 7860 is a different service.');help.setWordWrap(True);setup_form.addRow(help);self.setup=setup
        if seconds>600:
            note=Q.QLabel('This slideshow is longer than one generation. Matching sections will be created and crossfaded into one soundtrack.');note.setWordWrap(True);layout.addWidget(note)
        note=Q.QLabel('Using this result replaces the music playlist and keeps the photo timing shown here. Auto-Fit is turned off so the music follows your slideshow. Earlier music files are kept.');note.setWordWrap(True);layout.addWidget(note)
        self.status=Q.QLabel('Ready. First model loading can take several minutes.');self.status.setTextFormat(QtCore.Qt.PlainText);self.status.setWordWrap(True);outer.addWidget(self.status)
        self.progress=Q.QProgressBar();self.progress.setRange(0,0);self.progress.hide();outer.addWidget(self.progress)
        row=Q.QHBoxLayout();outer.addLayout(row);self.generate=Q.QPushButton('Generate music');self.generate.clicked.connect(self.begin);row.addWidget(self.generate);self.cancel_button=Q.QPushButton('Cancel generation');self.cancel_button.clicked.connect(self.cancel_generation);self.cancel_button.setEnabled(False);row.addWidget(self.cancel_button)
        row=Q.QHBoxLayout();outer.addLayout(row);self.play=Q.QPushButton('Play preview');self.play.clicked.connect(self.preview);self.play.setEnabled(False);row.addWidget(self.play);self.stop=Q.QPushButton('Stop preview');self.stop.clicked.connect(self.stop_preview);self.stop.setEnabled(False);row.addWidget(self.stop)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Cancel);self.use=buttons.addButton('Use this music',Q.QDialogButtonBox.AcceptRole);self.use.setEnabled(False);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
        self.refresh_takes();self.operation.currentIndexChanged.connect(self.operation_changed);self.operation_changed()
        self.refresh_descriptions()
        self.mode.currentIndexChanged.connect(self.mode_changed);self.mode_changed()
        self.lyrics.textChanged.connect(lambda:self.edit_generated.setEnabled(bool(self.lyrics.toPlainText().strip())))
        from ui_controls import protect_settings_wheel
        protect_settings_wheel(self)
        if parent and hasattr(parent,'shortcuts'):parent.shortcuts.bind(self,'close',self.reject)
    def refresh_takes(self,selected=None):
        self.takes.clear()
        for path in list_takes(ROOT/'Generated Music'):
            self.takes.addItem(path.name,str(path));self.takes.setItemData(self.takes.count()-1,str(path),QtCore.Qt.ToolTipRole)
        if selected:self.takes.setCurrentIndex(max(0,self.takes.findData(str(selected))))
        self.load_take_button.setEnabled(self.takes.count()>0)
    def restore_take_style(self,path):
        style=take_style(metadata_for(path))
        for key in ('era','genre','mood','voice','language'):
            if key in style:getattr(self,key).setCurrentText(style[key])
        for key in ('details','topic','lyrics'):
            if key in style:getattr(self,key).setPlainText(style[key])
        if 'music_mode' in style:self.mode.setCurrentIndex(max(0,self.mode.findData(style['music_mode'])))
    def load_selected_take(self):
        if self.takes.currentData():
            try:self.loaded(self.takes.currentData())
            except Exception as error:self.failed(str(error))
    def loaded(self,path):
        self.stop_preview()
        try:duration=music_duration(path,threading.Event())
        except Exception as error:self.failed('Could not load audio: '+str(error)[:400]);return
        self.source_path=path;self.source_seconds=duration;self.result_path=path
        self.edit_start.setValue(0);self.edit_end.setValue(duration);self.source_label.setText('Source: '+Path(path).name+' — '+format_time(duration))
        self.restore_take_style(path);self.refresh_takes(path);self.operation_changed();self.idle();self.status.setText('Loaded audio as the editing source. Choose an operation; each result becomes a new take.')
    def use_result_source(self):
        if self.result_path:
            try:self.loaded(self.result_path)
            except Exception as error:self.failed(str(error))
    def start_file_job(self,action,finished,message):
        if self.busy():return
        self.stop_preview();self.worker=AudioFileWorker(action,self);self.worker.done.connect(finished);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.idle)
        self.library_box.setEnabled(False);self.choices.setEnabled(False);self.setup.setEnabled(False);self.generate.setEnabled(False);self.use.setEnabled(False);self.play.setEnabled(False);self.cancel_button.setEnabled(True);self.progress.show();self.status.setText(message);self.worker.start()
    def import_audio(self):
        path,_=Q.QFileDialog.getOpenFileName(self,'Import or reload an audio track',str(Path.home()),'Audio (*.wav *.flac *.mp3 *.m4a *.aac *.aiff *.aif *.ogg *.opus *.wma);;All files (*)')
        if path:self.start_file_job(lambda cancel:import_take(path,ROOT/'Generated Music',cancel),self.loaded,'Copying the audio into your saved takes…')
    def save_audio(self):
        if not self.result_path:return
        path,selected=Q.QFileDialog.getSaveFileName(self,'Save this audio take',str(Path.home()/(Path(self.result_path).stem+'.wav')),'WAV audio (*.wav);;FLAC audio (*.flac);;MP3 audio (*.mp3)')
        if not path:return
        if not Path(path).suffix:path+=('.flac' if 'FLAC' in selected else '.mp3' if 'MP3' in selected else '.wav')
        # QFileDialog already confirms replacing an existing audio file. Never
        # allow export to overwrite a different internal working take.
        if Path(path).resolve().parent==(ROOT/'Generated Music').resolve() and Path(path).exists():self.failed('Choose a new name or an export folder; saved working takes are kept unchanged.');return
        sidecar=Path(path).with_suffix('.json')
        if sidecar.exists() and Q.QMessageBox.question(self,'Replace companion settings?','This name also has an existing JSON file. Replace it with this take’s lyrics and settings?',Q.QMessageBox.Yes|Q.QMessageBox.No,Q.QMessageBox.No)!=Q.QMessageBox.Yes:return
        source=self.result_path
        self.start_file_job(lambda cancel:export_take(source,path,cancel),lambda saved:self.status.setText('Audio saved: '+saved+' (companion settings are saved when available).'),'Saving the audio take…')
    def operation_changed(self):
        op=self.operation.currentData();self.edit_box.setVisible(op in ('repaint','layer'));self.range_label.setVisible(op=='repaint');self.range_widget.setVisible(op=='repaint')
        for widget in (self.instrument_label,self.instrument,self.layer_label,self.layer_volume):widget.setVisible(op=='layer')
        hints={'new':'Create a fresh take for the slideshow duration. Load an earlier take to restore its lyrics and style.',
        'repaint':'Replace only the selected seconds. Use my lyrics lets you revise the song text; keep the full song’s lyrics and change the desired lines. The original audio outside the passage is retained, with brief blends inside its edges. The edited passage may sound different.',
        'extend':'Add an ending to reach the slideshow length shown above. The existing song is retained except for a half-second join. Supply lyrics for the continuation, or select Instrumental. AI edits support up to ten minutes.',
        'trim':'Create a shorter copy at the slideshow length. No model is needed and the original is retained. The slideshow’s closing fade still applies during video export.',
        'layer':'Generate a separate instrument part and mix it over the original at the selected volume. Requires the ACE-Step Base model, which may download on first use. The original remains a separate take; the generated part is also kept. Musical fit can vary. Use Instrumental for accompaniment.'}
        self.edit_hint.setText(hints.get(op,''))
        if hasattr(self,'generate') and not self.busy():
            self.generate.setText('Create shorter copy' if op=='trim' else 'Create edited take' if op!='new' else 'Generate another take' if self.result_path else 'Generate music')
            self.choices.setEnabled(op!='trim')
    def refresh_descriptions(self,selected=None):
        self.saved_descriptions.clear();self.saved_descriptions.addItem('Choose a saved description…',None)
        try:presets=self.description_presets.load()
        except Exception as error:self.status.setText(str(error));presets={}
        for name in sorted(presets,key=str.casefold):
            self.saved_descriptions.addItem(name,name);self.saved_descriptions.setItemData(self.saved_descriptions.count()-1,presets[name][:240],QtCore.Qt.ToolTipRole)
        if selected is not None:self.saved_descriptions.setCurrentIndex(max(0,self.saved_descriptions.findData(selected)))
        self.remove_description_button.setEnabled(bool(presets))
    def load_description(self,index):
        name=self.saved_descriptions.itemData(index)
        if name is None:return
        try:
            text=self.description_presets.load()[name]
            self.details.selectAll();self.details.insertPlainText(text)
            warning=' This description mentions vocals; select a song mode for singing, or remove vocal directions for instrumental use.' if self.mode.currentData()=='instrumental' and any(word in text.lower() for word in ['vocal','female lead','male lead']) else ''
            self.status.setText('Loaded description: '+name+'. For its detailed style, you can select Genre → Use description only.'+warning)
        except Exception as error:self.status.setText('Could not load description: '+str(error)[:250])
    def save_description(self):
        text=self.details.toPlainText()
        if not text.strip():self.status.setText('Type a description before saving it.');return
        name,ok=Q.QInputDialog.getText(self,'Save description','Name for this description:',text=self.saved_descriptions.currentData() or '')
        if not ok:return
        try:
            presets=self.description_presets.load();existing=next((key for key in presets if key.casefold()==name.strip().casefold()),None)
            if existing is not None and presets[existing]!=text:
                if Q.QMessageBox.question(self,'Update saved description','Replace the saved text for “'+existing+'”?',Q.QMessageBox.Yes|Q.QMessageBox.No,Q.QMessageBox.No)!=Q.QMessageBox.Yes:return
            name=self.description_presets.save(name,text,replace=True);self.refresh_descriptions(name);self.status.setText('Description saved: '+name)
        except Exception as error:self.status.setText(str(error)[:400])
    def remove_description(self):
        name=self.saved_descriptions.currentData()
        if name is None:self.status.setText('Choose the saved description to remove.');return
        if Q.QMessageBox.question(self,'Remove saved description','Remove “'+name+'” from the saved list? The description in the editor will be kept.',Q.QMessageBox.Yes|Q.QMessageBox.No,Q.QMessageBox.No)!=Q.QMessageBox.Yes:return
        try:self.description_presets.remove(name);self.refresh_descriptions();self.status.setText('Removed saved description. The current text is still in the editor.')
        except Exception as error:self.status.setText(str(error)[:400])
    def mode_changed(self):
        mode=self.mode.currentData();self.vocal_panel.setVisible(mode!='instrumental');self.topic.setVisible(mode=='topic');self.topic_label.setVisible(mode=='topic');self.lyrics.setReadOnly(mode!='lyrics');self.edit_generated.setVisible(mode=='topic');self.edit_generated.setEnabled(bool(self.lyrics.toPlainText().strip()))
        self.lyrics_label.setText('Lyrics to review' if mode=='topic' else 'Your lyrics')
        hints={'instrumental':'Music without singing or spoken words.','topic':'Describe the subject. ACE-Step writes the lyrics and creates the song together. Returned lyrics can be reviewed, edited and reused afterward. Requires its language model; first loading may take longer.','lyrics':'Paste your words below. Verse and chorus tags are optional. Match the amount of text to the displayed duration; a short song may rush or omit lines. Vocal preference is guidance, not a guarantee.'}
        self.mode_hint.setText(hints[mode]+(' Vocal songs currently support up to ten minutes.' if mode!='instrumental' else ''))
    def style_options(self):
        return dict(era=self.era.currentText(),genre=self.genre.currentText(),mood=self.mood.currentText(),details=self.details.toPlainText(),music_mode=self.mode.currentData(),voice=self.voice.currentText(),language=self.language.currentText(),topic=self.topic.toPlainText(),lyrics=self.lyrics.toPlainText())
    def remember_style(self,style):
        if self.style_owner is not None and hasattr(self.style_owner,'project_music_style'):
            if self.style_owner.project_music_style!=style:
                self.style_owner.project_music_style=style;self.style_owner.project_changed()
    def pick_folder(self):
        folder=Q.QFileDialog.getExistingDirectory(self,'Choose the ACE-Step project folder',self.folder.text() or str(Path.home()))
        if folder:self.folder.setText(folder)
    def begin(self):
        if self.worker and self.worker.isRunning():return
        self.stop_preview();options=dict(self.style_options(),operation=self.operation.currentData(),source_audio=self.source_path,edit_start=self.edit_start.value(),edit_end=self.edit_end.value(),instrument=self.instrument.currentText(),layer_volume=self.layer_volume.value(),folder=self.folder.text().strip(),url=self.url.text().strip(),token=self.token.text(),logs=str(ROOT/'Logs'))
        try:
            from music_generator import local_url
            (validate_music_options(options,self.seconds) if options['operation']=='new' else validate_edit(options,self.seconds,self.source_seconds));local_url(options['url']);self.settings_path.parent.mkdir(parents=True,exist_ok=True);self.settings_path.write_text(json.dumps({k:v for k,v in options.items() if k!='logs'},indent=2))
        except Exception as error:self.status.setText(str(error)[:400]);return
        self.remember_style({key:options[key] for key in STYLE_KEYS})
        # Keep every auditioned result: regenerating never overwrites an earlier take.
        output=ROOT/'Generated Music'/('Slideshow Music '+uuid.uuid4().hex[:12]+'.wav')
        self.worker=MusicWorker(options,self.seconds,output,self);self.worker.message.connect(self.status.setText);self.worker.done.connect(self.generated);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.idle)
        self.library_box.setEnabled(False);self.choices.setEnabled(False);self.setup.setEnabled(False);self.generate.setEnabled(False);self.use.setEnabled(False);self.play.setEnabled(False);self.cancel_button.setEnabled(True);self.progress.show();self.status.setText('Connecting to the local music engine…');self.worker.start()
    def generated(self,path):
        try:metadata=json.loads(Path(path).with_suffix('.json').read_text())
        except (OSError,ValueError):metadata={}
        if metadata.get('mode')=='topic':
            text=metadata.get('lyrics','')
            if isinstance(text,str):
                self.lyrics.setPlainText(text);self.remember_style(self.style_options())
                try:
                    saved=json.loads(self.settings_path.read_text());saved.update(self.style_options());self.settings_path.write_text(json.dumps(saved,indent=2))
                except (OSError,ValueError):pass
        self.result_path=path;self.refresh_takes(path);self.status.setText('Ready: '+Path(path).name+' — '+format_time(metadata.get('requested_seconds',self.seconds))+'. Save this take, preview it, or use this music. Editing source is unchanged until you choose it.')
    def failed(self,message):self.status.setText(message)
    def idle(self):
        self.progress.hide();self.cancel_button.setEnabled(False);self.generate.setEnabled(True);self.generate.setText('Generate another take' if self.result_path else 'Generate music');self.library_box.setEnabled(True);self.save_audio_button.setEnabled(bool(self.result_path));self.use_source_button.setEnabled(bool(self.result_path));self.choices.setEnabled(True);self.setup.setEnabled(True);self.use.setEnabled(bool(self.result_path));self.play.setEnabled(bool(self.result_path));self.operation_changed()
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
        self.remember_style(self.style_options());self.stop_preview();super().accept()
    def closeEvent(self,event):
        if self.busy():self.cancel_generation();event.ignore()
        else:self.stop_preview();event.accept()
