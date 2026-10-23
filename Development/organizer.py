from pathlib import Path
import threading
from PySide6 import QtCore,QtWidgets as Q
from engine import VIDEO_EXT,video_info,music_duration,Cancelled
from timing import format_time
AUDIO={'.mp3','.m4a','.wav','.aac','.flac','.ogg','.aiff','.aif'}
IMAGE={'.png','.jpg','.jpeg','.jps','.tif','.tiff','.webp','.bmp'}
def path_of(item):return item.data(QtCore.Qt.UserRole)
def paths(widget):return [path_of(widget.item(i)) for i in range(widget.count())]
def audio_item(path,duration=None):
    item=Q.QListWidgetItem();item.setData(QtCore.Qt.UserRole,path);item.setToolTip(path);label_audio(item,duration);return item

def label_audio(item,duration):
    suffix=format_time(duration) if duration is not None and duration>=0 else 'reading duration…' if duration is None else 'duration unavailable'
    item.setText(Path(path_of(item)).name+' — '+suffix)

class DurationWorker(QtCore.QThread):
    found=QtCore.Signal(str,float,str)
    def __init__(self,files,parent=None):super().__init__(parent);self.files=files;self.cancel=threading.Event()
    def run(self):
        for path in self.files:
            if self.cancel.is_set():return
            try:
                duration=video_info(path,self.cancel)['duration'] if Path(path).suffix.lower() in VIDEO_EXT else music_duration(path,self.cancel)
                self.found.emit(path,duration,'')
            except Cancelled:return
            except Exception as e:self.found.emit(path,-1,str(e)[:200])

class DropList(Q.QListWidget):
    dropped=QtCore.Signal(list)
    def __init__(self):
        super().__init__();self.setDragDropMode(Q.QAbstractItemView.InternalMove);self.setSelectionMode(Q.QAbstractItemView.ExtendedSelection)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
        else:super().dragEnterEvent(e)
    def dragMoveEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
        else:super().dragMoveEvent(e)
    def dropEvent(self,e):
        if e.mimeData().hasUrls():self.dropped.emit([u.toLocalFile() for u in e.mimeData().urls()]);e.acceptProposedAction()
        else:super().dropEvent(e)

def move_selected(widget,direction):
    rows=sorted((widget.row(i) for i in widget.selectedItems()),reverse=direction>0)
    if not rows:return
    if min(rows)+direction<0 or max(rows)+direction>=widget.count():return
    for row in rows:
        item=widget.takeItem(row);widget.insertItem(row+direction,item);item.setSelected(True)

def remove_selected(widget):
    for item in widget.selectedItems():widget.takeItem(widget.row(item))

class Organizer(Q.QDialog):
    def __init__(self,main):
        super().__init__(main);self.main=main;self.setWindowTitle('Stereo Slideshow — Expanded Organizer');self.resize(1200,800)
        main.shortcuts.bind(self,'close',self.accept)
        layout=Q.QVBoxLayout(self);row=Q.QHBoxLayout();layout.addLayout(row)
        row.addWidget(Q.QLabel('Arrange your visual sequence and music playlist. Drag rows or use Move up / Move down.'))
        back=Q.QPushButton('− Return to main window');back.clicked.connect(self.accept);row.addWidget(back)
        split=Q.QSplitter();layout.addWidget(split,1)
        self.content=DropList();self.music=DropList()
        self.content.dropped.connect(self.add);self.music.dropped.connect(self.add)
        for title,widget in [('Photos and videos — playback order',self.content),('Music playlist — playback order',self.music)]:
            panel=Q.QWidget();box=Q.QVBoxLayout(panel);box.addWidget(Q.QLabel(title));box.addWidget(widget,1)
            buttons=Q.QHBoxLayout();box.addLayout(buttons)
            for text,fn in [('Add…',lambda _=False,w=widget:self.pick(w)),('Remove',lambda _=False,w=widget:remove_selected(w)),('Move up',lambda _=False,w=widget:move_selected(w,-1)),('Move down',lambda _=False,w=widget:move_selected(w,1))]:
                b=Q.QPushButton(text);b.clicked.connect(fn);buttons.addWidget(b)
            split.addWidget(panel)
        for i in range(main.files.count()):self.content.addItem(main.files.item(i).clone())
        for i in range(main.music_files.count()):self.music.addItem(main.music_files.item(i).clone())
        self.summary=Q.QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Save|Q.QDialogButtonBox.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        for widget in [self.content,self.music]:
            widget.model().rowsInserted.connect(self.refresh_durations);widget.model().rowsRemoved.connect(self.refresh_durations);widget.model().rowsMoved.connect(self.refresh_durations)
        self.refresh_durations()
    def pick(self,widget):
        title='Choose music files' if widget is self.music else 'Choose photos and videos'
        self.add(Q.QFileDialog.getOpenFileNames(self,title)[0])
    def add(self,files):
        existing=set(paths(self.content))
        for path in files:
            ext=Path(path).suffix.lower()
            if ext in AUDIO:self.music.addItem(audio_item(path,self.main.duration(path)))
            elif ext in IMAGE|VIDEO_EXT and path not in existing:
                item=Q.QListWidgetItem(Path(path).name);item.setData(QtCore.Qt.UserRole,path);item.setToolTip(path)
                if ext in VIDEO_EXT:item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable);item.setCheckState(QtCore.Qt.Unchecked if path in self.main.muted_paths else QtCore.Qt.Checked)
                self.content.addItem(item);existing.add(path)
        self.main.queue_probe(paths(self.content)+paths(self.music));self.refresh_durations()
    def refresh_durations(self,*args):
        total=0;pending=False
        for i in range(self.music.count()):
            item=self.music.item(i);d=self.main.duration(path_of(item));label_audio(item,d)
            if d is None or d<0:pending=True
            else:total+=d
        self.summary.setText(f'{self.content.count()} visual items · {self.music.count()} music tracks · Playlist: '+('reading durations…' if pending else format_time(total)))
    def apply(self):
        self.main.files.clear()
        for i in range(self.content.count()):self.main.files.addItem(self.content.item(i).clone())
        self.main.set_playlist(paths(self.music))
