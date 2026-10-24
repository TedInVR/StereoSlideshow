import sys, os, json, threading, traceback, datetime, tempfile
from pathlib import Path
if __name__=='__main__':
    from mac_identity import configure_macos_identity
    configure_macos_identity()
from PySide6 import QtCore, QtGui, QtWidgets as Q
from engine import render, Cancelled, RenderError, VIDEO_EXT
from timing import make_plan, describe_plan, TimingError, format_time
from organizer import Organizer, DurationWorker, audio_item, label_audio, paths as list_paths
IMAGE={'.png','.jpg','.jpeg','.jps','.tif','.tiff','.webp','.bmp'}
AUDIO={'.mp3','.m4a','.wav','.aac','.flac','.ogg','.aiff','.aif'}
def item_path(item):
    return item.data(QtCore.Qt.UserRole)

from app_paths import ROOT, SETTINGS, ICON, VERSION
class Worker(QtCore.QThread):
    update=QtCore.Signal(int,str); done=QtCore.Signal(list); failed=QtCore.Signal(str,str)
    def __init__(self,images,audio,out,cfg):
        super().__init__(); self.args=(images,audio,out,cfg); self.cancel=threading.Event()
    def run(self):
        try: self.done.emit(render(*self.args,self.update.emit,self.cancel))
        except Cancelled:self.failed.emit('Cancelled. Completed exports, if any, remain in the output folder.','')
        except Exception as e:
            message=str(e) if isinstance(e,RenderError) else 'The slideshow stopped unexpectedly. Your original photos, videos and music were not changed.'
            logfile=''
            try:
                folder=ROOT/'Logs';folder.mkdir(parents=True,exist_ok=True)
                path=folder/('render_error_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.txt')
                path.write_text(message+'\n\n'+traceback.format_exc()+'\n\n'+getattr(e,'details',''),encoding='utf-8');logfile=str(path)
            except OSError:pass
            self.failed.emit(message[:500],logfile)
class CaptionEditor(Q.QDialog):
    def __init__(self,paths,captions,front,parent):
        super().__init__(parent);self.setWindowTitle('Photo and video captions');self.resize(900,540)
        self.paths=paths;self.captions=dict(captions);self.current=None
        for path in paths:self.captions.setdefault(path,Path(path).stem)
        layout=Q.QVBoxLayout(self);layout.addWidget(Q.QLabel('Select an item, then type its caption. Leave blank for no caption.'))
        split=Q.QSplitter();layout.addWidget(split,1)
        self.list=Q.QListWidget();split.addWidget(self.list)
        right=Q.QWidget();panel=Q.QVBoxLayout(right);split.addWidget(right)
        self.name=Q.QLabel();self.name.setWordWrap(True);panel.addWidget(self.name)
        self.text=Q.QPlainTextEdit();self.text.setPlaceholderText('Type a caption for this photo or video…');panel.addWidget(self.text)
        self.count=Q.QLabel('');panel.addWidget(self.count);self.text.textChanged.connect(self.changed)
        b=Q.QPushButton('Clear this caption');b.clicked.connect(self.text.clear);panel.addWidget(b)
        self.front=Q.QCheckBox('Place captions slightly in front of the screen');self.front.setChecked(front);layout.addWidget(self.front)
        layout.addWidget(Q.QLabel('White text appears near the bottom in both eyes. Video captions stay for the full clip.'))
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Save|Q.QDialogButtonBox.Cancel);layout.addWidget(buttons);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject)
        for i,path in enumerate(paths):
            item=Q.QListWidgetItem(f'{i+1}. '+Path(path).name);item.setToolTip(path);self.list.addItem(item)
        self.list.currentRowChanged.connect(self.select);self.list.setCurrentRow(0)
    def changed(self):
        if self.current is not None:self.captions[self.current]=self.text.toPlainText()
        self.count.setText(f'{len(self.text.toPlainText())} / 400 characters')
    def select(self,row):
        if row<0:return
        self.current=self.paths[row];self.name.setText(Path(self.current).name);self.name.setToolTip(self.current)
        self.text.blockSignals(True);self.text.setPlainText(self.captions.get(self.current,''));self.text.blockSignals(False);self.changed()
    def save(self):
        if any(len(self.captions.get(path,''))>400 for path in self.paths):
            Q.QMessageBox.information(self,'Caption too long','Please keep each caption to 400 characters or fewer.');return
        self.accept()

from project_ui import ProjectMixin
class Window(ProjectMixin,Q.QWidget):
    durations_changed=QtCore.Signal()
    def __init__(self):
        super().__init__(); self.setWindowTitle('Stereo Slideshow — v'+VERSION); self.resize(1180,850); self.setAcceptDrops(True); self.worker=None
        try: saved=json.loads(SETTINGS.read_text())
        except Exception: saved={}
        self.muted_paths=set(saved.get('muted_videos',[])); self.captions=saved.get('captions',{}); self.caption_front=saved.get('caption_front',True)
        layout=Q.QVBoxLayout(self)
        self.menu=Q.QMenuBar(self);self.menu.setNativeMenuBar(True);layout.setMenuBar(self.menu)
        file_menu=self.menu.addMenu('File')
        help_menu=self.menu.addMenu('Help')
        help_menu.addAction('Check for Updates…',self.check_for_updates)
        folder_action=help_menu.addAction('Open Stereo Slideshow Folder');folder_action.triggered.connect(lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(ROOT))))
        setup_action=help_menu.addAction('Guided YouTube Setup…');setup_action.triggered.connect(self.setup_youtube)
        guide_action=help_menu.addAction('User Guide…');guide_action.triggered.connect(self.show_guide)
        walkthrough_action=help_menu.addAction('Guided Walkthrough…');walkthrough_action.triggered.connect(self.guided_walkthrough)
        heading=Q.QLabel('Stereo Slideshow'+(' — Experimental Windows version' if sys.platform=='win32' else '')); heading.setStyleSheet('font-size:26px;font-weight:600'); layout.addWidget(heading)
        columns=Q.QSplitter(QtCore.Qt.Horizontal);layout.addWidget(columns,1)
        left=Q.QWidget();left_layout=Q.QVBoxLayout(left);left_layout.setContentsMargins(0,0,8,0);columns.addWidget(left)
        right=Q.QWidget();right_layout=Q.QVBoxLayout(right);right_layout.setContentsMargins(0,0,0,0);columns.addWidget(right)
        left_layout.addWidget(Q.QLabel('Step 1 — Add and arrange content'))
        content_title=Q.QLabel('Content — Drag photos and music here');content_title.setWordWrap(True);content_title.setStyleSheet('font-weight:600');left_layout.addWidget(content_title)
        left_layout.addWidget(Q.QLabel('3D video clips are welcome too.'))
        scroll=Q.QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(Q.QFrame.NoFrame)
        panel=Q.QWidget();sections=Q.QVBoxLayout(panel);scroll.setWidget(panel);right_layout.addWidget(scroll,1)
        groups={}
        for key,title in [('music','Step 2 — Music playlist'),('timing','Step 3 — Timing'),('appearance','Step 4 — Picture and 3D'),('title','Step 5 — Opening title'),('export','Step 6 — Export and save')]:
            box=Q.QGroupBox(title);box.setStyleSheet('QGroupBox { font-weight:600; margin-top:10px; padding-top:12px; }');groups[key]=Q.QFormLayout(box);groups[key].setRowWrapPolicy(Q.QFormLayout.WrapLongRows);sections.addWidget(box)
        sections.addStretch();columns.setSizes([440,700])
        header=Q.QHBoxLayout();left_layout.addLayout(header);header.addStretch();expand=Q.QPushButton('+ Expand lists');expand.setToolTip('Open a nearly full-screen organizer for photos, videos and music');expand.clicked.connect(self.organize);header.addWidget(expand)
        self.files=Q.QListWidget(); self.files.setDragDropMode(Q.QAbstractItemView.InternalMove); self.files.setSelectionMode(Q.QAbstractItemView.ExtendedSelection); left_layout.addWidget(self.files,1)
        row=Q.QHBoxLayout(); left_layout.addLayout(row)
        for label,func in [('Add files…',self.pick),('Remove selected',self.remove),('Clear list',self.files.clear),('Captions…',self.edit_captions)]:
            b=Q.QPushButton(label); b.clicked.connect(func); row.addWidget(b)
        soundrow=Q.QHBoxLayout(); left_layout.addLayout(soundrow)
        hint=Q.QLabel('Checked videos play their original sound.');hint.setWordWrap(True);left_layout.addWidget(hint)
        for label,checked in [('Mute all clips',False),('Enable all clips',True)]:
            b=Q.QPushButton(label); b.clicked.connect(lambda _=False,c=checked:self.clip_sound(c)); soundrow.addWidget(b)
        self.audio='';self.music=Q.QLabel();self.music.setWordWrap(True);groups['music'].addRow(self.music)
        self.music_files=Q.QListWidget();self.music_files.setDragDropMode(Q.QAbstractItemView.InternalMove);self.music_files.setSelectionMode(Q.QAbstractItemView.ExtendedSelection);self.music_files.setFixedHeight(110);groups['music'].addRow(self.music_files)
        for path in saved.get('playlist',([saved['audio']] if saved.get('audio') else [])):self.music_files.addItem(audio_item(path))
        row=Q.QHBoxLayout();groups['music'].addRow(row)
        for text,fn in [('Add music…',self.pick_music),('Remove selected music',self.remove_music),('Clear music',self.clear_music)]:
            button=Q.QPushButton(text);button.clicked.connect(fn);row.addWidget(button)
        create_music=Q.QPushButton('Create music to fit this slideshow…');create_music.clicked.connect(self.create_music);groups['music'].addRow(create_music)
        form=Q.QFormLayout()
        self.title=Q.QLineEdit(saved.get('title','')); form.addRow('Opening title (optional)',self.title)
        self.sec=Q.QDoubleSpinBox(); self.sec.setDecimals(3);self.sec.setRange(1/30,86400);self.manual_seconds=saved.get('seconds_v3',5); self.sec.setValue(self.manual_seconds); self.sec.setSuffix(' seconds'); form.addRow('Seconds per photo',self.sec)
        self.end_mode=Q.QComboBox();self.end_mode.addItems(['Visual sequence ends the video','Music playlist ends the video']);self.end_mode.setCurrentIndex(saved.get('end_mode_index',0));form.addRow('End video with',self.end_mode)
        self.fit_music=Q.QCheckBox('Auto-Fit photos to music (seconds per photo)');self.fit_music.setChecked(saved.get('fit_music',False));form.addRow(self.fit_music)
        from ui_controls import TimingSummary
        self.timing_summary=TimingSummary('Add photos or videos to calculate timing.');form.addRow(self.timing_summary)
        self.animation=Q.QComboBox(); self.animation.addItems(['Zoom and pan','Subtle zoom and pan']); self.animation.setCurrentIndex(1 if saved.get('motion_style')=='Gentle' else 0); form.addRow('Photo animation',self.animation)
        self.drift=Q.QComboBox(); self.drift.addItems(['No pan (zoom only)','Very small','Small']); self.drift.setCurrentIndex(saved.get('drift_choice_v4',1)); form.addRow('Pan distance (subtle mode)',self.drift)
        self.closing=Q.QDoubleSpinBox(); self.closing.setRange(0,30); self.closing.setValue(saved.get('closing_fade',6)); self.closing.setSuffix(' seconds'); form.addRow('Closing fade to black + silence',self.closing)
        self.pause=Q.QDoubleSpinBox(); self.pause.setRange(0,10); self.pause.setValue(saved.get('pause',1)); form.addRow('Blank opening (seconds)',self.pause)
        self.title_sec=Q.QDoubleSpinBox(); self.title_sec.setRange(3,30); self.title_sec.setValue(saved.get('title_seconds',6)); form.addRow('Title duration (seconds)',self.title_sec)
        self.motion=Q.QComboBox(); self.motion.addItems(['Approach','Approach then retreat']); self.motion.setCurrentText(saved.get('title_motion','Approach then retreat')); form.addRow('Title depth movement',self.motion)
        self.res=Q.QComboBox(); self.res.addItems(['1080 pixels high per eye','2160 pixels high per eye','540 pixels high — quick test']); self.res.setCurrentIndex(saved.get('resolution',0)); form.addRow('Output resolution',self.res)
        self.aspect=Q.QComboBox(); self.aspect.addItems(['4:3','1:1','16:9','2:1']); self.aspect.setCurrentText(saved.get('eye_aspect','4:3')); form.addRow('Frame shape per eye',self.aspect)
        self.backdrop=Q.QComboBox(); self.backdrop.addItems(['Sharp moving current photo','Blurred current photo','Previous photo grows','Solid color']); self.backdrop.setCurrentText(saved.get('background_style_v6','Sharp moving current photo')); form.addRow('Background style',self.backdrop)
        self.layers=Q.QCheckBox('3D layers: background behind main photo, captions in front'); self.layers.setChecked(saved.get('depth_layers',True)); form.addRow(self.layers)
        self.layer_strength=Q.QComboBox(); self.layer_strength.addItems(['Subtle','Medium','Strong']); self.layer_strength.setCurrentIndex(saved.get('layer_strength',1)); form.addRow('Layer separation',self.layer_strength)
        self.cross=Q.QCheckBox('Input photos are cross-eye (right eye first)'); self.cross.setChecked(saved.get('cross',False)); form.addRow(self.cross)
        self.video_half=Q.QCheckBox('Video clips are half-SBS (squeezed eyes)'); self.video_half.setChecked(saved.get('video_half',False)); form.addRow(self.video_half)
        self.video_cross=Q.QCheckBox('Video clips are cross-eye (right eye first)'); self.video_cross.setChecked(saved.get('video_cross',False)); form.addRow(self.video_cross)
        self.video_sound=Q.QCheckBox('Allow checked clips to play sound (music lowers during them)'); self.video_sound.setChecked(saved.get('video_sound',True)); form.addRow(self.video_sound)
        self.bg=saved.get('background','#000000'); self.fg=saved.get('text_color','#ffffff')
        self.bgbutton=Q.QPushButton('Choose background…'); self.bgbutton.clicked.connect(lambda:self.color(False)); form.addRow('Background',self.bgbutton)
        self.fgbutton=Q.QPushButton('Choose title color…'); self.fgbutton.clicked.connect(lambda:self.color(True)); form.addRow('Title color',self.fgbutton)
        self.sbs=Q.QCheckBox('Full-SBS MP4 — normal proportions for local playback'); self.sbs.setChecked(saved.get('sbs',True)); self.ana=Q.QCheckBox('Dubois red/cyan anaglyph MP4'); self.ana.setChecked(saved.get('anaglyph',True)); form.addRow(self.sbs); self.yt=Q.QCheckBox('Extra YouTube compatibility MKV — appears squeezed in VLC'); self.yt.setChecked(saved.get('youtube_v4',False)); form.addRow(self.yt); form.addRow(self.ana)
        self.out=Q.QLineEdit(saved.get('output',str(Path.home()/'Movies/Stereo Slideshows'))); rr=Q.QHBoxLayout(); rr.addWidget(self.out); b=Q.QPushButton('Choose…'); b.clicked.connect(self.folder); rr.addWidget(b); form.addRow('Save finished videos',rr)
        self.source=Q.QCheckBox('Save in a Stereo Slideshows folder beside the first source item')
        self.source.setChecked(saved.get('source_output',True)); form.addRow(self.source)
        self.out.setEnabled(not self.source.isChecked()); self.source.toggled.connect(lambda checked:self.out.setEnabled(not checked))
        # Move the existing controls into clear, numbered categories.
        timing={self.sec,self.end_mode,self.fit_music,self.timing_summary,self.closing}
        titles={self.title,self.pause,self.title_sec,self.motion,self.fgbutton}
        exports={self.res,self.sbs,self.yt,self.ana,self.source}
        while form.rowCount():
            row=form.takeRow(0);label=row.labelItem.widget() if row.labelItem else None
            item=row.fieldItem;widget=item.widget() if item else None
            key='timing' if widget in timing else 'title' if widget in titles else 'export' if widget in exports or (label and label.text()=='Save finished videos') else 'appearance'
            field=widget if widget else item.layout()
            if label:groups[key].addRow(label,field)
            else:groups[key].addRow(field)
        self.bar=Q.QProgressBar();self.bar.hide();right_layout.addWidget(self.bar)
        self.status=Q.QLabel('Ready • Drag rows to arrange photos and videos.');self.status.setWordWrap(True);self.status.setTextFormat(QtCore.Qt.PlainText);self.status.setSizePolicy(Q.QSizePolicy.Ignored,Q.QSizePolicy.Preferred);right_layout.addWidget(self.status)
        rr=Q.QHBoxLayout();right_layout.addLayout(rr);self.preview=Q.QPushButton('Preview slideshow…');self.preview.clicked.connect(self.preview_slideshow);rr.addWidget(self.preview);self.start=Q.QPushButton('Create slideshow');self.start.clicked.connect(self.begin);rr.addWidget(self.start);self.stop=Q.QPushButton('Cancel');self.stop.setEnabled(False);self.stop.clicked.connect(self.cancel);rr.addWidget(self.stop)
        from shortcuts import ShortcutManager
        self.shortcuts=ShortcutManager(ROOT/'Settings/shortcuts.json')
        for name,callback in [('add',self.pick),('music',self.pick_music),('organize',self.organize),('captions',self.edit_captions),('render',self.begin),('guide',self.show_guide),('walkthrough',self.guided_walkthrough),('close',self.close)]:self.shortcuts.bind(self,name,callback)
        shortcuts_action=help_menu.addAction('Keyboard Shortcuts…');shortcuts_action.triggered.connect(lambda:self.shortcuts.edit(self))
        self._duration_cache={};self._probe_requests=set();self.probe=None;self._probe_stamps={}
        self.probe_timer=QtCore.QTimer(self);self.probe_timer.setSingleShot(True);self.probe_timer.timeout.connect(self._start_probe)
        self.calc_timer=QtCore.QTimer(self);self.calc_timer.setSingleShot(True);self.calc_timer.timeout.connect(self.refresh_timing)
        for widget in [self.files,self.music_files]:
            widget.model().rowsInserted.connect(self.schedule_timing);widget.model().rowsRemoved.connect(self.schedule_timing);widget.model().rowsMoved.connect(self.schedule_timing)
        for widget in [self.sec,self.pause,self.title_sec,self.closing]:widget.valueChanged.connect(self.schedule_timing)
        self.title.textChanged.connect(self.schedule_timing);self.fit_music.toggled.connect(self.fit_changed);self.end_mode.currentIndexChanged.connect(self.end_changed)
        self.sec.setEnabled(not self.fit_music.isChecked());self.musiclabel();self.schedule_timing()
        self.animation_help=Q.QLabel();self.animation_help.setWordWrap(True);self.animation_help.setSizePolicy(Q.QSizePolicy.Ignored,Q.QSizePolicy.Preferred)
        groups['appearance'].insertRow(1,self.animation_help)
        self.animation.currentIndexChanged.connect(self.describe_animation);self.describe_animation()
        from ui_controls import protect_settings_wheel
        protect_settings_wheel(self)
        self.setup_projects(file_menu)
        file_menu.addAction('Export editable timeline for DaVinci Resolve…',self.export_resolve)
        resolve_button=Q.QPushButton('Export editable timeline for DaVinci Resolve…');resolve_button.clicked.connect(self.export_resolve);groups['export'].addRow(resolve_button)
        file_menu.addSeparator();action=file_menu.addAction('Upload finished SBS video to YouTube…');action.triggered.connect(self.upload_youtube)
        self.preview_job=False;self.preview_temp=None;self.last_exports=[]
        self.watch=Q.QPushButton('Watch finished video');self.watch.setEnabled(False);self.watch.clicked.connect(self.watch_finished);groups['export'].addRow(self.watch)
        self.upload_button=Q.QPushButton('Upload finished video to YouTube…');self.upload_button.clicked.connect(self.upload_youtube);groups['export'].addRow(self.upload_button)
        note=Q.QLabel('Watch your finished video first. Uploading is a separate step and only starts when you click Upload in the YouTube window.');note.setWordWrap(True);groups['export'].addRow(note)
    def check_for_updates(self):
        if self.project_busy():self.status.setText('Finish the current operation before checking for updates.');return
        from update_dialog import UpdateDialog
        dialog=UpdateDialog(self);dialog.exec()
    def setup_youtube(self):
        from youtube_dialog import YouTubeDialog
        dialog=YouTubeDialog(self,title=self.title.text());QtCore.QTimer.singleShot(0,dialog.setup_guide);dialog.exec()
    def upload_youtube(self):
        from youtube_dialog import YouTubeDialog
        source=next((path for path in self.last_exports if '_Full_SBS_' in Path(path).name and Path(path).suffix.lower()=='.mp4' and Path(path).is_file()),'')
        dialog=YouTubeDialog(self,source,getattr(self,'last_export_title',self.title.text()) if source else self.title.text());dialog.synthetic.setChecked(any('Generated Music' in Path(path).parts for path in self.playlist()));dialog.exec()
    def watch_finished(self):
        path=next((p for p in self.last_exports if Path(p).is_file() and Path(p).suffix.lower()=='.mp4'),None)
        if path is None:path=next((p for p in self.last_exports if Path(p).is_file()),None)
        if path:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        else:self.status.setText('The finished video has moved or is unavailable. Open it from its saved folder.')
    def preview_slideshow(self):
        if self.project_busy():self.status.setText('Finish or cancel the current operation first.');return
        if not self.files.count():Q.QMessageBox.information(self,'Add photos or videos','Add photos or videos before previewing.');return
        dialog=Q.QDialog(self);dialog.setWindowTitle('Quick slideshow preview');dialog.resize(520,260)
        layout=Q.QVBoxLayout(dialog)
        text=Q.QLabel('Build a temporary 270-high, 15-fps video, then open it in your video player. This still takes processing time; long video clips can take longer. It shows the sequence, effects and sound, with lower detail and less smooth motion than the final video. Your chosen final resolution and saved videos stay unchanged.');text.setWordWrap(True);layout.addWidget(text)
        view=Q.QComboBox();view.addItems(['Side-by-side 3D','Red/cyan anaglyph (for glasses)']);layout.addWidget(view)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Ok|Q.QDialogButtonBox.Cancel);buttons.button(Q.QDialogButtonBox.Ok).setText('Build preview');buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==Q.QDialog.Accepted:self.begin(preview=True,preview_anaglyph=view.currentIndex()==1)

    def describe_animation(self):
        subtle=self.animation.currentIndex()==1
        self.animation_help.setText('Keeps the whole photo visible, with a 2% zoom change and very small horizontal, vertical or diagonal movement. Pan distance controls how far it moves.' if subtle else 'Alternates close-up zooms with left/right and up/down movement. Close-up zooms crop the top and bottom; side-moving photos are shown large. The pan-distance setting applies only to Subtle zoom and pan.')
        self.drift.setEnabled(subtle)
        self.animation.setToolTip(self.animation_help.text())
        self.drift.setToolTip('For Subtle zoom and pan only. Very small: up to 0.3% of the frame width or height over a photo; Small: up to 0.6%. Available margins can reduce movement.')
    def show_guide(self):
        dialog=Q.QDialog(self);dialog.setWindowTitle('Stereo Slideshow — User Guide');dialog.resize(900,720)
        layout=Q.QVBoxLayout(dialog);browser=Q.QTextBrowser();browser.setOpenExternalLinks(False)
        path=Path(__file__).with_name('User_Guide.html');browser.setSource(QtCore.QUrl.fromLocalFile(str(path)));layout.addWidget(browser,1)
        row=Q.QHBoxLayout();search=Q.QLineEdit();search.setPlaceholderText('Find in guide…');row.addWidget(search)
        def find():
            if not browser.find(search.text()):
                cursor=browser.textCursor();cursor.movePosition(QtGui.QTextCursor.Start);browser.setTextCursor(cursor);browser.find(search.text())
        button=Q.QPushButton('Find next');button.clicked.connect(find);search.returnPressed.connect(find);row.addWidget(button);layout.addLayout(row)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec()
    def guided_walkthrough(self):
        if self.worker and self.worker.isRunning():
            Q.QMessageBox.information(self,'Rendering','Finish or cancel the current render before starting the walkthrough.');return
        from walkthrough import Walkthrough
        wizard=Walkthrough(self,CaptionEditor)
        result=wizard.exec();wizard.cleanup()
        if result==Q.QDialog.Accepted:
            wizard.apply();self.project_changed();self.begin()
    def edit_captions(self):
        if self.worker and self.worker.isRunning():
            Q.QMessageBox.information(self,'Rendering','Wait for rendering to finish before editing captions.');return
        if not self.files.count():
            Q.QMessageBox.information(self,'Add photos or videos','Add your photos and videos first, then open Captions.');return
        dialog=CaptionEditor([item_path(self.files.item(i)) for i in range(self.files.count())],self.captions,self.caption_front,self)
        if dialog.exec()==Q.QDialog.Accepted:
            self.captions=dialog.captions;self.caption_front=dialog.front.isChecked()
            # Save captions immediately, including when the user has not rendered yet.
            try:settings=json.loads(SETTINGS.read_text())
            except Exception:settings={}
            settings.update(captions=self.captions,caption_front=self.caption_front)
            SETTINGS.parent.mkdir(parents=True,exist_ok=True);SETTINGS.write_text(json.dumps(settings,indent=2));self.project_changed()
    def clip_sound(self,checked):
        if checked: self.video_sound.setChecked(True)
        for i in range(self.files.count()):
            item=self.files.item(i)
            if Path(item_path(item)).suffix.lower() in VIDEO_EXT:
                item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
    def playlist(self):return list_paths(self.music_files)
    def set_playlist(self,paths):
        self.music_files.clear()
        for path in paths:self.music_files.addItem(audio_item(path,self.duration(path)))
        self.musiclabel();self.schedule_timing()
    def musiclabel(self):
        playlist=self.playlist();self.audio=playlist[0] if playlist else ''
        total=0;ready=True
        for i in range(self.music_files.count()):
            item=self.music_files.item(i);d=self.duration(item_path(item));label_audio(item,d)
            if d is None or d<0:ready=False
            else:total+=d
        self.music.setText('Music: none' if not playlist else f'Music playlist: {len(playlist)} track(s) — '+(format_time(total) if ready else 'reading durations…'))
    def create_music(self):
        if self.worker and self.worker.isRunning():Q.QMessageBox.information(self,'Rendering','Finish or cancel rendering before generating music.');return
        if not self.files.count():Q.QMessageBox.information(self,'Add content first','Add photos and video clips, then choose their display time before creating music.');return
        cfg=self.timing_config();cfg.update(end_mode='visuals',fit_music=False)
        paths=[item_path(self.files.item(i)) for i in range(self.files.count())]
        plan,message=self.preview_for(paths,[],cfg)
        if plan is None:Q.QMessageBox.information(self,'Slideshow timing',message);return
        from music_dialog import MusicDialog
        dialog=MusicDialog(plan['total']/plan['fps'],self)
        if dialog.exec()==Q.QDialog.Accepted:
            self.end_mode.setCurrentIndex(0);self.fit_music.setChecked(False);self.sec.setValue(cfg['seconds'])
            self.set_playlist([dialog.result_path]);self.schedule_timing()
            self.status.setText('Generated music added. The slideshow uses the photo timing from your music request. If you change the timeline, generate a new soundtrack to match it.')
    def pick_music(self):
        self.set_playlist(self.playlist()+Q.QFileDialog.getOpenFileNames(self,'Add music tracks')[0])
    def remove_music(self):
        for item in self.music_files.selectedItems():self.music_files.takeItem(self.music_files.row(item))
        self.musiclabel();self.schedule_timing()
    def clear_music(self):self.set_playlist([])
    def organize(self):
        if self.worker and self.worker.isRunning():Q.QMessageBox.information(self,'Rendering','Finish or cancel rendering before reorganizing the project.');return
        dialog=Organizer(self);self.durations_changed.connect(dialog.refresh_durations)
        dialog.setWindowState(dialog.windowState()|QtCore.Qt.WindowMaximized)
        try:
            if dialog.exec()==Q.QDialog.Accepted:dialog.apply();self.schedule_timing()
        finally:self.durations_changed.disconnect(dialog.refresh_durations)
    def stamp(self,path):
        try:s=Path(path).stat();return (s.st_size,s.st_mtime_ns)
        except OSError:return None
    def duration(self,path):
        record=getattr(self,'_duration_cache',{}).get(path)
        return record[1] if record and record[0]==self.stamp(path) else None
    def queue_probe(self,paths):
        if not hasattr(self,'probe_timer'):return
        self._probe_requests.update(p for p in paths if Path(p).suffix.lower() in AUDIO|VIDEO_EXT);self.probe_timer.start(120)
    def _start_probe(self):
        if self.probe is not None:return
        needed=[p for p in self._probe_requests if self.duration(p) is None]
        if not needed:return
        self._probe_stamps={p:self.stamp(p) for p in needed};worker=DurationWorker(needed,self);self.probe=worker
        worker.found.connect(self._duration_found);worker.finished.connect(lambda w=worker:self._probe_done(w));worker.start()
    def _duration_found(self,path,seconds,error):
        self._duration_cache[path]=(self._probe_stamps.get(path),seconds,error);self.musiclabel();self.calc_timer.start(20);self.durations_changed.emit()
    def _probe_done(self,worker):
        if self.probe is worker:self.probe=None
        worker.deleteLater();self.probe_timer.start(50)
    def schedule_timing(self,*args):
        if not hasattr(self,'calc_timer'):return
        self.queue_probe([item_path(self.files.item(i)) for i in range(self.files.count())]+self.playlist());self.calc_timer.start(100)
    def fit_changed(self,checked):
        if checked:
            self.manual_seconds=self.sec.value();self.end_mode.setCurrentIndex(1)
        else:
            self.sec.blockSignals(True);self.sec.setValue(self.manual_seconds);self.sec.blockSignals(False)
        self.sec.setEnabled(not checked);self.schedule_timing()
    def end_changed(self,index):
        if index==0 and self.fit_music.isChecked():self.fit_music.setChecked(False)
        self.schedule_timing()
    def timing_config(self):
        return dict(fps=30,seconds=self.sec.value(),pause=self.pause.value(),title=self.title.text(),title_seconds=self.title_sec.value(),closing_fade=self.closing.value(),end_mode='music' if self.end_mode.currentIndex()==1 else 'visuals',fit_music=self.fit_music.isChecked())
    def preview_for(self,media,playlist,cfg):
        self.queue_probe(media+playlist);durations=[];music_seconds=0
        for path in media+playlist:
            if path in playlist or Path(path).suffix.lower() in VIDEO_EXT:
                d=self.duration(path)
                if d is None:return None,'Reading durations… '+Path(path).name
                if d<0:return None,'Could not read duration: '+Path(path).name
        for path in media:durations.append(self.duration(path) if Path(path).suffix.lower() in VIDEO_EXT else None)
        for path in playlist:music_seconds+=self.duration(path)
        try:plan=make_plan(durations,music_seconds if playlist else None,cfg)
        except TimingError as e:return None,str(e)
        return plan,describe_plan(plan,music_seconds if playlist else None)
    def refresh_timing(self):
        self.musiclabel()
        if not self.files.count():self.timing_summary.setText('Add photos or videos to calculate timing.');return
        plan,text=self.preview_for([item_path(self.files.item(i)) for i in range(self.files.count())],self.playlist(),self.timing_config())
        self.timing_summary.setText(text)
        if self.fit_music.isChecked() and plan and plan['photo_count']:
            self.sec.blockSignals(True);self.sec.setValue(plan['photo_seconds']);self.sec.blockSignals(False)
        self.sec.setToolTip('Calculated automatically from the music length.' if self.fit_music.isChecked() else 'Duration of each photo; video clips keep their full length.')
    def color(self,title):
        c=Q.QColorDialog.getColor(QtGui.QColor(self.fg if title else self.bg),self)
        if c.isValid():
            if title: self.fg=c.name(); self.fgbutton.setText(self.fg)
            else: self.bg=c.name(); self.bgbutton.setText(self.bg)
            self.project_changed()
    def folder(self):
        p=Q.QFileDialog.getExistingDirectory(self,'Output folder',self.out.text())
        if p: self.source.setChecked(False); self.out.setText(p)
    def pick(self): self.add(Q.QFileDialog.getOpenFileNames(self,'Choose stereo photos, videos, and music')[0])
    def remove(self):
        for item in self.files.selectedItems(): self.files.takeItem(self.files.row(item))
    def add(self,paths):
        if len(paths)==1 and Path(paths[0]).suffix.lower()=='.stereoslideshow':self.open_project(paths[0]);return
        if self.worker and self.worker.isRunning(): return
        existing={item_path(self.files.item(i)) for i in range(self.files.count())}; unsupported=[]
        for p in sorted(paths,key=lambda x:x.lower()):
            if Path(p).suffix.lower() in (IMAGE | VIDEO_EXT) and p not in existing:
                item=Q.QListWidgetItem(Path(p).name);item.setData(QtCore.Qt.UserRole,p);item.setToolTip(p)
                if Path(p).suffix.lower() in VIDEO_EXT:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.Unchecked if p in self.muted_paths else QtCore.Qt.Checked)
                    item.setToolTip(p+'\nChecked: keep this video’s sound. Unchecked: mute clip sound.')
                self.files.addItem(item); existing.add(p)
            elif Path(p).suffix.lower() in AUDIO:self.music_files.addItem(audio_item(p,self.duration(p)))
            else: unsupported.append(Path(p).name)
        self.musiclabel();self.schedule_timing()
        if unsupported: self.status.setText('Skipped unsupported files: '+', '.join(unsupported))
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self,e): self.add([u.toLocalFile() for u in e.mimeData().urls()]); e.acceptProposedAction()
    def export_resolve(self):
        if self.project_busy():self.status.setText('Finish the current render or project save first.');return
        if not self.files.count():Q.QMessageBox.information(self,'Add photos or videos','Add at least one photo or video first.');return
        from resolve_dialog import ResolveDialog
        cfg=self.timing_config();h=[1080,2160,540][self.res.currentIndex()]
        num,den=map(int,self.aspect.currentText().split(':'))
        cfg.update(width=4*round(h*num/den/2),height=h,video_sound=self.video_sound.isChecked(),cross=self.cross.isChecked(),video_half=self.video_half.isChecked(),video_cross=self.video_cross.isChecked())
        dialog=ResolveDialog(self,self.project_snapshot(),cfg);dialog.exec()
    def begin(self,preview=False,preview_anaglyph=False):
        if self.project_worker is not None and self.project_worker.isRunning():return
        if self.worker and self.worker.isRunning(): return
        if not self.files.count(): Q.QMessageBox.information(self,'Add photos','Drop some SBS photos or video clips first.'); return
        if not preview and not(self.sbs.isChecked() or self.ana.isChecked() or self.yt.isChecked()): Q.QMessageBox.information(self,'Choose output','Select at least one output format.'); return
        h=[1080,2160,540][self.res.currentIndex()]
        num,den=map(int,self.aspect.currentText().split(':')); eye_w=2*round(h*num/den/2); w=eye_w*2
        output=str(Path(item_path(self.files.item(0))).parent/'Stereo Slideshows') if self.source.isChecked() else self.out.text()
        self.actual_output=output
        cfg=dict(playlist=self.playlist(),end_mode_index=self.end_mode.currentIndex(),end_mode='music' if self.end_mode.currentIndex()==1 else 'visuals',fit_music=self.fit_music.isChecked(),depth_layers=self.layers.isChecked(),layer_strength=self.layer_strength.currentIndex(),captions=self.captions,caption_front=self.caption_front,muted_videos=[item_path(self.files.item(i)) for i in range(self.files.count()) if Path(item_path(self.files.item(i))).suffix.lower() in VIDEO_EXT and self.files.item(i).checkState()==QtCore.Qt.Unchecked],closing_fade=self.closing.value(),video_half=self.video_half.isChecked(),video_cross=self.video_cross.isChecked(),video_sound=self.video_sound.isChecked(),motion_style=['Closer zoom and side drift','Gentle'][self.animation.currentIndex()],background_style_v6=self.backdrop.currentText(),eye_aspect=self.aspect.currentText(),background_style=self.backdrop.currentText(),drift=[0,.0015,.003][self.drift.currentIndex()],drift_choice_v4=self.drift.currentIndex(),width=w,height=h,fps=30,seconds=self.sec.value(),seconds_v3=self.manual_seconds if self.fit_music.isChecked() else self.sec.value(),pause=self.pause.value(),title_seconds=self.title_sec.value(),title=self.title.text(),title_motion=self.motion.currentText(),background=self.bg,text_color=self.fg,cross=self.cross.isChecked(),sbs=self.sbs.isChecked(),youtube=self.yt.isChecked(),youtube_v4=self.yt.isChecked(),source_output=self.source.isChecked(),anaglyph=self.ana.isChecked(),audio=self.audio,output=self.out.text(),resolution=self.res.currentIndex())
        if cfg['end_mode']=='music' or cfg['fit_music']:
            plan,message=self.preview_for([item_path(self.files.item(i)) for i in range(self.files.count())],self.playlist(),cfg)
            if plan is None:
                Q.QMessageBox.information(self,'Timing calculator',message);return
        if preview:
            if self.preview_temp:self.preview_temp.cleanup()
            self.preview_temp=tempfile.TemporaryDirectory(prefix='StereoSlideshow-preview-')
            output=self.preview_temp.name
            ph=270;pw=4*round(ph*num/den/2)
            cfg.update(width=pw,height=ph,fps=15,sbs=not preview_anaglyph,anaglyph=preview_anaglyph,youtube=False,preview=True)
        else:
            SETTINGS.parent.mkdir(parents=True,exist_ok=True);SETTINGS.write_text(json.dumps(cfg,indent=2));self.muted_paths=set(cfg['muted_videos'])
            self.render_title=cfg['title']
        self.preview_job=preview
        self.worker=Worker([item_path(self.files.item(i)) for i in range(self.files.count())],self.playlist(),output,cfg)
        self.worker.update.connect(self.progress); self.worker.done.connect(self.finished); self.worker.failed.connect(self.error)
        self.bar.setValue(0);self.bar.show();self.preview.setEnabled(False);self.start.setEnabled(False); self.stop.setEnabled(True); self.worker.start()
    def progress(self,n,s): self.bar.show();self.bar.setValue(n); self.status.setText(('Preview: ' if self.preview_job else '')+s)
    def cancel(self):
        if self.worker: self.worker.cancel.set(); self.status.setText('Cancelling…')
    def finished(self,files):
        self.bar.hide();self.preview.setEnabled(True);self.start.setEnabled(True);self.stop.setEnabled(False)
        if self.preview_job:
            self.preview_job=False
            self.status.setText('Preview ready. Watch it in your video player, adjust settings if needed, then click Create slideshow for the final video. Preview files are temporary.')
            if files:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(files[0]))
            return
        self.last_exports=list(files);self.last_export_title=getattr(self,'render_title',self.title.text());self.watch.setEnabled(bool(files))
        self.status.setText('Finished. Click Watch finished video to review it. Use Upload finished video to YouTube when you are happy with it.\n'+'\n'.join(files))
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.actual_output))
    def error(self,s,logfile=''):
        self.preview_job=False
        self.bar.hide();self.preview.setEnabled(True)
        self.start.setEnabled(True);self.stop.setEnabled(False);self.status.setText(s[:240])
        if s.startswith('Cancelled.'):return
        # Keep the explanation bounded; raw encoder output never controls window size.
        dialog=Q.QDialog(self);dialog.setWindowTitle('Slideshow could not finish');dialog.resize(620,240)
        screen=self.screen().availableGeometry();dialog.setMaximumSize(min(700,screen.width()-40),min(620,screen.height()-60))
        layout=Q.QVBoxLayout(dialog)
        label=Q.QLabel(s[:500]);label.setTextFormat(QtCore.Qt.PlainText);label.setWordWrap(True);label.setObjectName('error-summary');layout.addWidget(label)
        layout.addWidget(Q.QLabel('Your original files have not been changed.'))
        details=Q.QPlainTextEdit();details.setReadOnly(True);details.setLineWrapMode(Q.QPlainTextEdit.NoWrap);details.setMaximumHeight(240);details.hide();layout.addWidget(details)
        if logfile:
            note=Q.QLabel('A diagnostic report was saved in the app’s Logs folder.');note.setWordWrap(True);layout.addWidget(note)
            row=Q.QHBoxLayout();layout.addLayout(row)
            show=Q.QPushButton('Show technical details');row.addWidget(show)
            def toggle():
                if details.isHidden():
                    try:text=Path(logfile).read_text(encoding='utf-8')[-100000:]
                    except OSError:text='The diagnostic report could not be opened.'
                    details.setPlainText(text);details.show();show.setText('Hide technical details')
                else:details.hide();show.setText('Show technical details')
                dialog.adjustSize()
            show.clicked.connect(toggle)
            folder=Q.QPushButton('Open Logs folder');folder.clicked.connect(lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(logfile).parent))));row.addWidget(folder)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        close=buttons.button(Q.QDialogButtonBox.Close);close.setDefault(True);close.setFocus()
        dialog.exec()

    def closeEvent(self,e):
        if self.worker and self.worker.isRunning():self.cancel();e.ignore();return
        if self.project_worker is not None and self.project_worker.isRunning():
            self.project_worker.cancel.set();e.ignore();return
        if not getattr(self,'pending_app_update',None) and not self.project_can_replace(self.close):e.ignore();return
        if self.worker and self.worker.isRunning(): self.cancel(); e.ignore()
        else:
            if self.probe is not None and self.probe.isRunning():
                self.probe.cancel.set()
                if not self.probe.wait(2000):e.ignore();return
            if getattr(self,'pending_app_update',None):
                try:
                    from update_core import launch_installer
                    launch_installer(ROOT,self.pending_app_update,os.getpid());self.pending_app_update=None
                except Exception as error:
                    Q.QMessageBox.warning(self,'Update could not start',str(error)[:400]);e.ignore();return
            e.accept()
class Application(Q.QApplication):
    def event(self,e):
        if e.type()==QtCore.QEvent.FileOpen and hasattr(self,'window'): self.window.add([e.file()]); return True
        return super().event(e)
if __name__=='__main__':
    QtCore.QCoreApplication.setApplicationName('Stereo Slideshow');QtCore.QCoreApplication.setOrganizationName('Ted Witten')
    Application.setApplicationDisplayName('Stereo Slideshow')
    app=Application(sys.argv)
    if ICON.is_file():app.setWindowIcon(QtGui.QIcon(str(ICON)))
    (ROOT/'Runtime').mkdir(parents=True,exist_ok=True)
    lock=QtCore.QLockFile(str(ROOT/'Runtime'/'app.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        Q.QMessageBox.information(None,'Stereo Slideshow','Stereo Slideshow is already running. Select its existing window or Dock icon.');sys.exit(0)
    import atexit
    running=ROOT/'Runtime'/'running.json';running.write_text(json.dumps({'pid':os.getpid()}))
    def release():
        try:
            if json.loads(running.read_text()).get('pid')==os.getpid():running.unlink()
        except (OSError,ValueError):pass
        lock.unlock()
    atexit.register(release)
    app.setStyle('Fusion'); win=Window(); app.window=win; win.show()
    if len(sys.argv)>1: win.add(sys.argv[1:])
    sys.exit(app.exec())
