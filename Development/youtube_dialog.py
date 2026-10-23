"""Reviewable YouTube upload plans and a cancellable account/upload worker."""
import json, threading, tempfile
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets as Q
from app_paths import ROOT
from music_generator import MusicCancelled
from youtube_upload import (YouTubeClient,YouTubeError,UploadCancelled,DEFAULT_DESCRIPTION,
    atomic_json,load_json,client_config,video_metadata,prepare_stereo)

class YouTubeWorker(QtCore.QThread):
    message=QtCore.Signal(str);progress=QtCore.Signal(int);browser=QtCore.Signal(str);done=QtCore.Signal(dict);failed=QtCore.Signal(str)
    def __init__(self,action,parent):super().__init__(parent);self.action=action;self.cancel=threading.Event()
    def run(self):
        try:self.done.emit(self.action(self))
        except (UploadCancelled,MusicCancelled):self.failed.emit('Cancelled. Local videos are safe. If the final upload chunk had already reached YouTube, check Studio before retrying.')
        except Exception as error:self.failed.emit(str(error)[:650])

class YouTubeDialog(Q.QDialog):
    def __init__(self,parent=None,source='',title='',arm=False,plan=None):
        super().__init__(parent);self.setWindowTitle('YouTube — review upload' if not arm else 'YouTube — upload after this render');self.resize(720,760)
        self.worker=None;self.arm=arm;self.plan=None;self.client=YouTubeClient();self.connected=None;self.uploaded=False
        self.settings_path=ROOT/'Settings/youtube_upload.json';self.config_path=ROOT/'Settings/youtube_client.json';saved=load_json(self.settings_path)
        outer=Q.QVBoxLayout(self);scroll=Q.QScrollArea();scroll.setWidgetResizable(True);panel=Q.QWidget();layout=Q.QVBoxLayout(panel);scroll.setWidget(panel);outer.addWidget(scroll,1)
        group=Q.QGroupBox('1 — Connect your YouTube channel');form=Q.QFormLayout(group);layout.addWidget(group)
        self.channel=Q.QLabel('Not connected');self.channel.setTextFormat(QtCore.Qt.PlainText);self.channel.setWordWrap(True);form.addRow(self.channel)
        row=Q.QHBoxLayout();self.config_button=Q.QPushButton('Choose Google client JSON…');self.config_button.clicked.connect(self.pick_config);row.addWidget(self.config_button);self.connect_button=Q.QPushButton('Connect / change channel…');self.connect_button.clicked.connect(self.connect_account);row.addWidget(self.connect_button);form.addRow(row)
        row=Q.QHBoxLayout();self.disconnect_button=Q.QPushButton('Disconnect');self.disconnect_button.clicked.connect(self.disconnect);row.addWidget(self.disconnect_button);self.setup_button=Q.QPushButton('YouTube setup guide');self.setup_button.clicked.connect(self.setup_guide);row.addWidget(self.setup_button);form.addRow(row)
        note=Q.QLabel('First connection requires a Google Desktop OAuth client JSON and YouTube Data API v3 enabled in its project. Sign in on Google’s own page. Renewable access is stored in macOS Keychain; the app does not receive your Google password.');note.setWordWrap(True);form.addRow(note)
        self.fields=Q.QGroupBox('2 — Video and publishing details');form=Q.QFormLayout(self.fields);layout.addWidget(self.fields)
        self.file=Q.QLineEdit(source);self.file.setReadOnly(True);row=Q.QHBoxLayout();row.addWidget(self.file);self.pick_button=Q.QPushButton('Choose video…');self.pick_button.clicked.connect(self.pick_file);self.pick_button.setEnabled(not arm);row.addWidget(self.pick_button);form.addRow('Video',row)
        self.file.setPlaceholderText('The finished SBS video from this render' if arm else 'Choose a finished full-SBS video')
        self.layout_choice=Q.QComboBox();self.layout_choice.addItems(['Full-SBS — each eye has normal proportions','Half-SBS — each eye is squeezed horizontally']);form.addRow('Input layout',self.layout_choice)
        self.stereo_confirm=Q.QCheckBox('This is rectangular left/right SBS (left eye first), not anaglyph or VR180');self.stereo_confirm.setChecked(bool(source) or arm);form.addRow(self.stereo_confirm)
        self.title=Q.QLineEdit(title or (Path(source).stem.split('_StereoSlideshow_')[0] if source else ''));form.addRow('YouTube title',self.title)
        self.template=Q.QPlainTextEdit(saved.get('description_template',DEFAULT_DESCRIPTION));self.template.setFixedHeight(90);form.addRow('Reusable description template',self.template)
        label=Q.QLabel('Use {title} or {filename} where needed. Apply template fills the description below; you can then edit it. Before rendering, {filename} uses the proposed title.');label.setWordWrap(True);form.addRow(label)
        row=Q.QHBoxLayout();apply=Q.QPushButton('Apply template');apply.clicked.connect(self.apply_template);row.addWidget(apply);save=Q.QPushButton('Save template and default tags');save.clicked.connect(self.save_defaults);row.addWidget(save);form.addRow(row)
        self.description=Q.QPlainTextEdit();self.description.setMinimumHeight(125);self.description.setMaximumHeight(210);form.addRow('Video description',self.description)
        self.tags=Q.QLineEdit(saved.get('tags','3D, stereoscopic, Stereo Slideshow'));self.tags.setPlaceholderText('Comma-separated tags');form.addRow('Tags',self.tags)
        self.privacy=Q.QComboBox()
        for label,value in [('Private — only you and invited viewers','private'),('Unlisted — anyone with the link','unlisted'),('Public — visible to everyone','public')]:self.privacy.addItem(label,value)
        form.addRow('Visibility',self.privacy)
        self.kids=Q.QComboBox();self.kids.addItem('Choose whether this video is made for kids',None);self.kids.addItem('No, it is not made for kids',False);self.kids.addItem('Yes, it is made for kids',True);form.addRow('Audience',self.kids)
        self.synthetic=Q.QCheckBox('Disclose altered or synthetic content to YouTube');form.addRow(self.synthetic)
        notice=Q.QLabel('For example, YouTube requires disclosure for synthetically generated music. Select this when using ACE-Step music or other content that needs disclosure.');notice.setWordWrap(True);form.addRow(notice)
        note=Q.QLabel('The uploader prepares a tagged MKV copy without re-encoding. Uploads may take time; YouTube must finish its own processing before 3D playback is available. Keep this app open until the upload finishes.');note.setWordWrap(True);form.addRow(note)
        notice=Q.QLabel("By clicking ‘Upload to YouTube’ or authorizing upload after this render, you certify that the content complies with the <a href='https://www.youtube.com/t/terms'>YouTube Terms of Service</a> (including the Community Guidelines). Please be sure not to violate others’ copyright or privacy rights. <a href='https://policies.google.com/privacy'>Google Privacy Policy</a>.");notice.setWordWrap(True);notice.setOpenExternalLinks(True);outer.addWidget(notice)
        self.status=Q.QLabel('Ready. Nothing is uploaded until you click Upload, or explicitly arm uploading after this render.');self.status.setTextFormat(QtCore.Qt.PlainText);self.status.setWordWrap(True);outer.addWidget(self.status)
        self.bar=Q.QProgressBar();self.bar.hide();outer.addWidget(self.bar)
        row=Q.QHBoxLayout();outer.addLayout(row);self.go=Q.QPushButton('Use these settings for this render' if arm else 'Upload to YouTube');self.go.clicked.connect(self.submit);row.addWidget(self.go);self.cancel_button=Q.QPushButton('Cancel');self.cancel_button.clicked.connect(self.reject);row.addWidget(self.cancel_button)
        self.open_video=Q.QPushButton('Open uploaded video');self.open_video.hide();self.open_video.clicked.connect(self.open_result);row.addWidget(self.open_video);self.result_url=''
        self.apply_template();self.refresh_connection()
        if plan:
            self.plan=dict(plan)
            self.title.setText(plan['title']);self.description.setPlainText(plan['description']);self.tags.setText(plan.get('tags',''));self.privacy.setCurrentIndex(max(0,self.privacy.findData(plan['privacy'])));self.kids.setCurrentIndex(self.kids.findData(plan['made_for_kids']));self.synthetic.setChecked(plan.get('synthetic',False));self.layout_choice.setCurrentIndex(1 if plan.get('half_sbs') else 0)
        from ui_controls import protect_settings_wheel
        protect_settings_wheel(self)
        if parent and hasattr(parent,'shortcuts'):parent.shortcuts.bind(self,'close',self.reject)
    def setup_guide(self):
        url=QtCore.QUrl.fromLocalFile(str(ROOT/'Development/User_Guide.html'));url.setFragment('youtube');QtGui.QDesktopServices.openUrl(url)
    def refresh_connection(self):
        try:
            account=self.client.store.load();self.connected=account.get('channel') if account else None
            self.channel.setText('Connected: '+self.connected['title']+'\nChannel ID: '+self.connected['id'] if self.connected else 'Not connected — choose client JSON, then Connect.')
        except Exception as error:self.connected=None;self.channel.setText(str(error))
        self.disconnect_button.setEnabled(bool(self.connected))
    def pick_config(self):
        path,_=Q.QFileDialog.getOpenFileName(self,'Choose Google Desktop OAuth client JSON',str(Path.home()/'Downloads'),'JSON (*.json)')
        if not path:return
        try:
            config=client_config(path)
            existing=load_json(self.config_path).get('installed',{})
            if self.connected and existing.get('client_id')!=config['client_id']:raise YouTubeError('Disconnect the current channel before choosing a different Google client.')
            atomic_json(self.config_path,{'installed':config});self.status.setText('Desktop client saved. Click Connect to authorize your channel.')
        except Exception as error:self.status.setText(str(error))
    def pick_file(self):
        path,_=Q.QFileDialog.getOpenFileName(self,'Choose a finished rectangular SBS video',str(Path.home()/'Movies'),'SBS videos (*.mp4 *.mkv *.mov *.m4v)')
        if path:
            self.file.setText(path);self.stereo_confirm.setChecked(False)
            if not self.title.text():self.title.setText(Path(path).stem.split('_StereoSlideshow_')[0]);self.apply_template()
    def apply_template(self):self.description.setPlainText(self.template.toPlainText().replace('{title}',self.title.text()).replace('{filename}',Path(self.file.text()).name if self.file.text() else self.title.text()))
    def save_defaults(self):
        try:atomic_json(self.settings_path,{'description_template':self.template.toPlainText(),'tags':self.tags.text()});self.status.setText('Description template and default tags saved. Visibility still starts at Private for each new upload.')
        except Exception as error:self.status.setText('Could not save defaults: '+str(error)[:250])
    def start_job(self,action,done):
        if self.busy():return
        self.worker=YouTubeWorker(action,self);self.worker.message.connect(self.status.setText);self.worker.progress.connect(self.upload_progress);self.worker.browser.connect(self.open_browser);self.worker.done.connect(done);self.worker.failed.connect(self.status.setText);self.worker.finished.connect(self.idle)
        self.fields.setEnabled(False);self.config_button.setEnabled(False);self.connect_button.setEnabled(False);self.disconnect_button.setEnabled(False);self.go.setEnabled(False);self.bar.setRange(0,0);self.bar.show();self.cancel_button.setText('Cancel task');self.worker.start()
    def open_browser(self,url):
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):self.status.setText('Could not open Google sign-in. Check your default browser and try connecting again.')
    def upload_progress(self,n):self.bar.setRange(0,100);self.bar.setValue(n)
    def connect_account(self):
        try:client_config(self.config_path)
        except Exception as error:self.status.setText(str(error));return
        self.start_job(lambda w:self.client.connect(self.config_path,w.cancel,w.browser.emit,w.message.emit),self.connected_done)
    def connected_done(self,value):self.refresh_connection();self.status.setText('Connected to '+value['title']+'. Review the publishing details below.')
    def disconnect(self):
        self.start_job(lambda w:(self.client.disconnect() or {}),lambda value:(self.refresh_connection(),self.status.setText('Disconnected. This does not delete any uploaded videos.')))
    def reviewed_plan(self):
        if not self.connected:raise YouTubeError('Connect your intended YouTube channel first.')
        if not self.stereo_confirm.isChecked():raise YouTubeError('Confirm that this is left-eye-first rectangular SBS. Anaglyph and VR180 need different handling.')
        if not self.arm and not Path(self.file.text()).is_file():raise YouTubeError('Choose a finished SBS video file.')
        plan=dict(title=self.title.text(),description=self.description.toPlainText(),tags=self.tags.text(),privacy=self.privacy.currentData(),made_for_kids=self.kids.currentData(),synthetic=self.synthetic.isChecked(),channel_id=self.connected['id'],channel_title=self.connected['title'],half_sbs=self.layout_choice.currentIndex()==1)
        video_metadata(plan);return plan
    def submit(self):
        if self.busy():return
        try:plan=self.reviewed_plan()
        except Exception as error:self.status.setText(str(error));return
        self.plan=plan
        if self.arm:super().accept();return
        source=self.file.text()
        self.start_job(lambda w:self.perform_upload(source,plan,w),self.upload_done)
    def perform_upload(self,source,plan,worker):
        with tempfile.TemporaryDirectory(prefix='stereo-youtube-') as temp:
            tagged=prepare_stereo(source,temp,worker.cancel,worker.message.emit,plan.get('half_sbs',False))
            return self.client.upload(tagged,plan,worker.cancel,worker.message.emit,worker.progress.emit)
    def start_armed(self):
        if self.plan and not self.busy():self.start_job(lambda w:self.perform_upload(self.file.text(),self.plan,w),self.upload_done)
    def upload_done(self,result):
        self.uploaded=True;self.result_url=result['url'];self.open_video.show();self.status.setText('Upload received by YouTube ('+result['privacy']+'). Processing may still be underway.\n'+result['url'])
        try:
            path=ROOT/'Settings/youtube_upload_history.json';history=load_json(path,{'uploads':[]});history['uploads']=(history.get('uploads',[])+[dict(result,title=self.plan['title'])])[-100:];atomic_json(path,history)
        except (OSError,TypeError):pass
    def open_result(self):
        if self.result_url:QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.result_url))
    def busy(self):return self.worker is not None and self.worker.isRunning()
    def idle(self):
        self.bar.hide();self.fields.setEnabled(not self.uploaded);self.config_button.setEnabled(True);self.connect_button.setEnabled(True);self.disconnect_button.setEnabled(bool(self.connected));self.go.setEnabled(not self.uploaded);self.cancel_button.setText('Close' if self.uploaded else 'Cancel')
    def reject(self):
        if self.busy():self.worker.cancel.set();self.status.setText('Cancelling… A network request may take up to 30 seconds to return.');return
        super().reject()
    def closeEvent(self,event):
        if self.busy():self.reject();event.ignore()
        else:event.accept()
