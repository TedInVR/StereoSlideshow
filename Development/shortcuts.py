"""Persistent, window-scoped keyboard shortcuts."""
import json, weakref
from PySide6 import QtCore, QtGui, QtWidgets as Q
ACTIONS={'add':('Add content','Ctrl+O'),'music':('Add music','Ctrl+Shift+O'),'organize':('Expand lists','Ctrl+E'),'captions':('Edit captions','Ctrl+Shift+C'),'render':('Create slideshow','Ctrl+Return'),'guide':('User guide','F1'),'walkthrough':('Guided walkthrough','Ctrl+Shift+G'),'close':('Close current window / save organizer changes','Ctrl+W')}
class ShortcutManager:
    def __init__(self,path):
        self.path=path;self.bindings=[]
        try:self.keys=json.loads(path.read_text())
        except (OSError,ValueError):self.keys={}
    def sequence(self,name):return QtGui.QKeySequence(self.keys.get(name,ACTIONS[name][1]))
    def bind(self,parent,name,callback):
        shortcut=QtGui.QShortcut(self.sequence(name),parent);shortcut.setContext(QtCore.Qt.WindowShortcut);shortcut.activated.connect(callback)
        self.bindings.append((name,weakref.ref(shortcut)));return shortcut
    def save(self,keys):
        self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(keys,indent=2));temporary.replace(self.path);self.keys=keys
        alive=[]
        for name,ref in self.bindings:
            shortcut=ref()
            try:
                if shortcut is not None:shortcut.setKey(self.sequence(name));alive.append((name,ref))
            except RuntimeError:pass
        self.bindings=alive
    def edit(self,parent):
        dialog=Q.QDialog(parent);dialog.setWindowTitle('Keyboard Shortcuts');dialog.resize(640,480);layout=Q.QVBoxLayout(dialog)
        note=Q.QLabel('Click a shortcut and press your preferred keys. Clear it to disable it. On Mac, Ctrl shortcuts use Command. In the expanded organizer, Close saves changes and returns to the main window.');note.setWordWrap(True);layout.addWidget(note)
        form=Q.QFormLayout();layout.addLayout(form);editors={}
        for name,(label,default) in ACTIONS.items():
            editor=Q.QKeySequenceEdit(self.sequence(name));editor.setMaximumSequenceLength(1);form.addRow(label,editor);editors[name]=editor
        status=Q.QLabel();status.setWordWrap(True);layout.addWidget(status)
        buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Save|Q.QDialogButtonBox.Cancel|Q.QDialogButtonBox.RestoreDefaults);layout.addWidget(buttons)
        def save():
            keys={name:editor.keySequence().toString(QtGui.QKeySequence.PortableText) for name,editor in editors.items()};used={}
            for name,key in keys.items():
                if key and key in used:status.setText('Choose different keys for '+ACTIONS[name][0]+' and '+ACTIONS[used[key]][0]+'.');return
                if key:used[key]=name
            try:self.save(keys)
            except OSError as error:status.setText('Could not save shortcuts: '+str(error));return
            dialog.accept()
        def defaults():
            for name,editor in editors.items():editor.setKeySequence(QtGui.QKeySequence(ACTIONS[name][1]))
        buttons.accepted.connect(save);buttons.rejected.connect(dialog.reject);buttons.button(Q.QDialogButtonBox.RestoreDefaults).clicked.connect(defaults);self.bind(dialog,'close',dialog.reject);dialog.exec()
