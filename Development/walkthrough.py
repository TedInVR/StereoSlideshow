from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets as Q
from engine import VIDEO_EXT
from organizer import audio_item,label_audio,paths as audio_paths,move_selected,remove_selected
IMAGE={'.png','.jpg','.jpeg','.jps','.tif','.tiff','.webp','.bmp'}
AUDIO={'.mp3','.m4a','.wav','.aac','.flac','.ogg','.aiff','.aif'}

def path_of(item):return item.data(QtCore.Qt.UserRole)
class MediaList(Q.QListWidget):
    urlsDropped=QtCore.Signal(list)
    def __init__(self):
        super().__init__();self.setAcceptDrops(True);self.setDragDropMode(Q.QAbstractItemView.InternalMove);self.setSelectionMode(Q.QAbstractItemView.ExtendedSelection)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
        else:super().dragEnterEvent(e)
    def dragMoveEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
        else:super().dragMoveEvent(e)
    def dropEvent(self,e):
        if e.mimeData().hasUrls():self.urlsDropped.emit([u.toLocalFile() for u in e.mimeData().urls()]);e.acceptProposedAction()
        else:super().dropEvent(e)
class Page(Q.QWizardPage):
    def validatePage(self):return self.check() if hasattr(self,'check') else True

class Walkthrough(Q.QWizard):
    def __init__(self,main,caption_editor):
        super().__init__(main);self.main=main;self.caption_editor=caption_editor
        self.setWindowTitle('Stereo Slideshow — Guided Walkthrough');self.resize(840,700)
        self.setWizardStyle(Q.QWizard.ClassicStyle);self.setOption(Q.QWizard.HaveHelpButton,True);self.helpRequested.connect(main.show_guide)
        self.setButtonText(Q.QWizard.FinishButton,'Create slideshow')
        self.captions=dict(main.captions);self.caption_front=main.caption_front;self.bg=main.bg;self.fg=main.fg
        self.controls={}
        page,body=self.add_step('1 of 6 — What would you like to make?','Choose your finished video formats. You can go Back to revise any choice.')
        self.clone_check(body,'sbs','Full-SBS MP4 — normal proportions for local viewing')
        self.clone_check(body,'ana','Red/cyan anaglyph MP4')
        self.clone_check(body,'yt','Extra YouTube compatibility MKV — may look squeezed locally')
        body.addRow(Q.QLabel('The existing injector settings are kept for the optional YouTube copy.'))
        page.check=self.check_outputs
        page,body=self.add_step('2 of 6 — Which photos and videos, and in what order?','Drop media here or choose Add files. Drag rows to reorder. Video checkboxes control original sound.')
        self.media=MediaList();body.addRow(self.media);self.media.urlsDropped.connect(self.add)
        for i in range(main.files.count()):self.media.addItem(main.files.item(i).clone())
        row=Q.QHBoxLayout();body.addRow(row)
        for label,fn in [('Add files…',self.pick),('Remove selected',self.remove),('Mute all clips',lambda:self.sound(False)),('Enable all clips',lambda:self.sound(True))]:
            b=Q.QPushButton(label);b.clicked.connect(fn);row.addWidget(b)
        page.check=self.check_media
        page,body=self.add_step('3 of 6 — How should it look and move?','Photo timing applies to photos. Automatic fitting keeps full clips when the music has enough time.')
        for name,label in [('sec','Seconds per photo'),('end_mode','End video with'),('aspect','Frame shape per eye'),('res','Resolution'),('animation','Photo animation'),('drift','Pan distance (subtle mode)'),('backdrop','Photo background'),('layer_strength','3D layer separation'),('closing','Closing fade (seconds)')]:self.clone_field(body,name,label)
        for name,label in [('fit_music','Auto-Fit photos to music (seconds per photo)'),('layers','Separate background, main photo, and caption depth'),('cross','Photos are cross-eye'),('video_half','Video clips are half-SBS'),('video_cross','Video clips are cross-eye'),('video_sound','Allow checked clips to play sound; lower music during them')]:self.clone_check(body,name,label)
        page,body=self.add_step('4 of 6 — What title and captions would you like?','A blank title skips the title section. Captions are optional and follow each item.')
        self.clone_field(body,'title','Opening title');self.clone_field(body,'pause','Blank opening (seconds)');self.clone_field(body,'title_sec','Title duration (seconds)');self.clone_field(body,'motion','Title depth movement')
        for label,is_title in [('Choose background color…',False),('Choose title color…',True)]:
            b=Q.QPushButton(label);b.clicked.connect(lambda _=False,t=is_title:self.color(t));body.addRow(b)
        b=Q.QPushButton('Edit captions for these photos and videos…');b.clicked.connect(self.edit_captions);body.addRow(b)
        body.addRow(Q.QLabel('Caption defaults use filenames without extensions. Clear a caption to leave it off.'))
        page,body=self.add_step('5 of 6 — Music and save location','Music loops automatically. Original clip sound is controlled by the checkboxes in Step 2.')
        self.playlist=Q.QListWidget();self.playlist.setDragDropMode(Q.QAbstractItemView.InternalMove);self.playlist.setSelectionMode(Q.QAbstractItemView.ExtendedSelection);body.addRow('Music playlist — drag to reorder',self.playlist)
        for path in main.playlist():self.playlist.addItem(audio_item(path,main.duration(path)))
        row=Q.QHBoxLayout();body.addRow(row)
        b=Q.QPushButton('Choose music…');b.clicked.connect(self.pick_music);row.addWidget(b)
        b=Q.QPushButton('No music');b.clicked.connect(self.playlist.clear);row.addWidget(b)
        b=Q.QPushButton('Remove selected');b.clicked.connect(lambda:remove_selected(self.playlist));row.addWidget(b)
        self.clone_check(body,'source','Save beside first source item in a Stereo Slideshows subfolder')
        self.output=Q.QLineEdit(main.out.text());body.addRow('Other output folder',self.output)
        self.controls['source'].toggled.connect(lambda checked:self.output.setEnabled(not checked));self.output.setEnabled(not self.controls['source'].isChecked())
        b=Q.QPushButton('Choose output folder…');b.clicked.connect(self.pick_output);body.addRow(b)
        page.check=self.check_locations
        page,body=self.add_step('6 of 6 — Ready to create your slideshow?','Review the choices below. Create slideshow applies them and starts rendering.')
        self.review=Q.QPlainTextEdit();self.review.setReadOnly(True);body.addRow(self.review)
        page.check=self.check_timing
        self.currentIdChanged.connect(self.refresh_review)
        self.main.durations_changed.connect(self.duration_update)
        self.controls['fit_music'].toggled.connect(self.fit_changed)
        self.controls['end_mode'].currentIndexChanged.connect(self.end_changed)
        self.controls['sec'].setEnabled(not self.controls['fit_music'].isChecked())
        self.controls['animation'].setToolTip(self.main.animation.toolTip())
        self.controls['drift'].setToolTip(self.main.drift.toolTip())
        def motion_changed():
            self.controls['drift'].setEnabled(self.controls['animation'].currentIndex()==1)
            self.controls['animation'].setToolTip('Zoom and pan: close-up crops and large side-moving photos. Subtle zoom and pan: keeps the full photo visible, changes zoom by 2%, and uses very small movement.')
        self.controls['animation'].currentIndexChanged.connect(motion_changed);motion_changed()
        from ui_controls import protect_settings_wheel
        protect_settings_wheel(self)
    def add_step(self,title,subtitle):
        page=Page();page.setTitle(title);page.setSubTitle(subtitle)
        outer=Q.QVBoxLayout(page);scroll=Q.QScrollArea();scroll.setWidgetResizable(True);panel=Q.QWidget();form=Q.QFormLayout(panel);scroll.setWidget(panel);outer.addWidget(scroll);self.addPage(page);return page,form
    def clone_check(self,form,name,label):
        original=getattr(self.main,name);w=Q.QCheckBox(label);w.setChecked(original.isChecked());self.controls[name]=w;form.addRow(w)
    def clone_field(self,form,name,label):
        original=getattr(self.main,name)
        if isinstance(original,Q.QComboBox):
            w=Q.QComboBox();w.addItems([original.itemText(i) for i in range(original.count())]);w.setCurrentIndex(original.currentIndex())
        elif isinstance(original,Q.QDoubleSpinBox):
            w=Q.QDoubleSpinBox();w.setRange(original.minimum(),original.maximum());w.setDecimals(original.decimals());w.setValue(original.value());w.setSuffix(original.suffix())
        else:w=Q.QLineEdit(original.text())
        self.controls[name]=w;form.addRow(label,w)
    def message(self,text):Q.QMessageBox.information(self,'Guided Walkthrough',text);return False
    def check_outputs(self):return any(self.controls[n].isChecked() for n in ['sbs','ana','yt']) or self.message('Choose at least one output format.')
    def check_media(self):return bool(self.media.count()) or self.message('Add at least one photo or video before continuing.')
    def check_locations(self):
        if any(not Path(path).is_file() for path in audio_paths(self.playlist)):return self.message('A music file could not be found. Choose another file or remove it from the playlist.')
        if not self.controls['source'].isChecked() and not self.output.text().strip():return self.message('Choose an output folder or save beside the first source item.')
        return True
    def pick(self):self.add(Q.QFileDialog.getOpenFileNames(self,'Choose SBS photos and videos')[0])
    def add(self,paths):
        existing={path_of(self.media.item(i)) for i in range(self.media.count())};skipped=[]
        for path in sorted(paths,key=str.lower):
            ext=Path(path).suffix.lower()
            if ext in IMAGE|VIDEO_EXT and path not in existing:
                item=Q.QListWidgetItem(Path(path).name);item.setData(QtCore.Qt.UserRole,path);item.setToolTip(path)
                if ext in VIDEO_EXT:item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable);item.setCheckState(QtCore.Qt.Unchecked if path in self.main.muted_paths else QtCore.Qt.Checked)
                self.media.addItem(item);existing.add(path)
            elif ext in AUDIO:self.playlist.addItem(audio_item(path,self.main.duration(path)))
            elif path not in existing:skipped.append(Path(path).name)
        self.main.queue_probe([path_of(self.media.item(i)) for i in range(self.media.count())]+audio_paths(self.playlist))
        if skipped:self.message('Unsupported items were skipped: '+', '.join(skipped))
    def remove(self):
        for item in self.media.selectedItems():self.media.takeItem(self.media.row(item))
    def sound(self,enabled):
        for i in range(self.media.count()):
            item=self.media.item(i)
            if Path(path_of(item)).suffix.lower() in VIDEO_EXT:item.setCheckState(QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked)
        if enabled:self.controls['video_sound'].setChecked(True)
    def color(self,title):
        c=Q.QColorDialog.getColor(QtGui.QColor(self.fg if title else self.bg),self)
        if c.isValid():
            if title:self.fg=c.name()
            else:self.bg=c.name()
    def edit_captions(self):
        dialog=self.caption_editor([path_of(self.media.item(i)) for i in range(self.media.count())],self.captions,self.caption_front,self)
        if dialog.exec()==Q.QDialog.Accepted:self.captions=dialog.captions;self.caption_front=dialog.front.isChecked()
    def pick_music(self):
        files=Q.QFileDialog.getOpenFileNames(self,'Choose music tracks')[0]
        for path in files:self.playlist.addItem(audio_item(path,self.main.duration(path)))
        self.main.queue_probe(files)
    def pick_output(self):
        path=Q.QFileDialog.getExistingDirectory(self,'Choose output folder',self.output.text())
        if path:self.output.setText(path);self.controls['source'].setChecked(False)
    def refresh_review(self,page):
        if page!=5:return
        paths=[path_of(self.media.item(i)) for i in range(self.media.count())]
        folder=str(Path(paths[0]).parent/'Stereo Slideshows') if paths and self.controls['source'].isChecked() else self.output.text()
        formats=[self.controls[n].text() for n in ['sbs','ana','yt'] if self.controls[n].isChecked()]
        lines=['OUTPUTS: '+', '.join(formats),'SAVE TO: '+folder,'MUSIC: '+(' → '.join(Path(path).name for path in audio_paths(self.playlist)) or 'none'),f"MANUAL PHOTO SETTING: {self.controls['sec'].value():g} seconds (unused when automatic fit is enabled).",f"FRAME: {self.controls['aspect'].currentText()} per eye; {self.controls['res'].currentText()}",f"CLOSING FADE: {self.controls['closing'].value():g} seconds",'TITLE: '+(self.controls['title'].text() or 'none'),'ANIMATION: '+self.controls['animation'].currentText(),'BACKGROUND: '+self.controls['backdrop'].currentText(),'3D LAYERS: '+(self.controls['layer_strength'].currentText() if self.controls['layers'].isChecked() else 'off'),'VIDEO INPUT: '+('half-SBS' if self.controls['video_half'].isChecked() else 'full-SBS')+(' / right eye first' if self.controls['video_cross'].isChecked() else ' / left eye first'),'','ORDER:']
        for i,path in enumerate(paths):
            video=Path(path).suffix.lower() in VIDEO_EXT;item=self.media.item(i)
            sound=' — sound on' if video and self.controls['video_sound'].isChecked() and item.checkState()==QtCore.Qt.Checked else ' — muted' if video else ''
            lines.append(f'{i+1}. {Path(path).name}{sound}')
            if self.captions.get(path,'').strip():lines.append('   Caption: '+self.captions[path].replace('\n',' / '))
        plan,calculation=self.main.preview_for(paths,audio_paths(self.playlist),self.timing_config())
        self.review.setPlainText(calculation+'\n\n'+'\n'.join(lines))
    def timing_config(self):
        c=self.controls
        return dict(fps=30,seconds=c['sec'].value(),pause=c['pause'].value(),title=c['title'].text(),title_seconds=c['title_sec'].value(),closing_fade=c['closing'].value(),end_mode='music' if c['end_mode'].currentIndex()==1 else 'visuals',fit_music=c['fit_music'].isChecked())
    def check_timing(self):
        if self.controls['end_mode'].currentIndex()==0 and not self.controls['fit_music'].isChecked():return True
        plan,message=self.main.preview_for([path_of(self.media.item(i)) for i in range(self.media.count())],audio_paths(self.playlist),self.timing_config())
        return plan is not None or self.message(message)
    def fit_changed(self,checked):
        if checked:self.controls['end_mode'].setCurrentIndex(1)
        self.controls['sec'].setEnabled(not checked)
    def end_changed(self,index):
        if index==0:self.controls['fit_music'].setChecked(False)
    def duration_update(self):
        for i in range(self.playlist.count()):
            item=self.playlist.item(i);label_audio(item,self.main.duration(path_of(item)))
        self.refresh_review(self.currentId())
    def cleanup(self):
        self.main.durations_changed.disconnect(self.duration_update)
    def apply(self):
        for name,source in self.controls.items():
            dest=getattr(self.main,name)
            if isinstance(source,Q.QCheckBox):dest.setChecked(source.isChecked())
            elif isinstance(source,Q.QComboBox):dest.setCurrentIndex(source.currentIndex())
            elif isinstance(source,Q.QDoubleSpinBox):dest.setValue(source.value())
            else:dest.setText(source.text())
        self.main.files.clear()
        for i in range(self.media.count()):self.main.files.addItem(self.media.item(i).clone())
        self.main.set_playlist(audio_paths(self.playlist));self.main.out.setText(self.output.text().strip())
        self.main.bg=self.bg;self.main.fg=self.fg;self.main.captions=self.captions;self.main.caption_front=self.caption_front
        self.main.bgbutton.setText(self.bg);self.main.fgbutton.setText(self.fg)
