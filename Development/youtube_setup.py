"""A resumable, page-by-page guide for a user's own Google Desktop client.

Google pages stay in the user's normal browser. This guide never asks for a
password, displays a client secret, or claims to verify a Google-side step.
"""
import re
from pathlib import Path
from urllib.parse import urlencode
from PySide6 import QtCore,QtGui,QtWidgets as Q
from app_paths import ROOT
from youtube_upload import SCOPES,atomic_json,load_json,client_config

STEPS=[
 ('Welcome — connect your own YouTube channel','Welcome'),
 ('Create a Google project','Google project'),
 ('Enable the YouTube service','Enable YouTube'),
 ('Set up the Google permission screen','Permission screen'),
 ('Allow your Google account to test the connection','Test account'),
 ('Choose the two YouTube permissions','Permissions'),
 ('Create and download the Desktop connection file','Download JSON'),
 ('Return to this Mac app and connect','Connect')]

class SetupPage(Q.QWizardPage):
    def __init__(self,title,subtitle,confirm=False,parent=None):
        super().__init__(parent);self.setTitle(title);self.setSubTitle(subtitle)
        outer=Q.QVBoxLayout(self);scroll=Q.QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(Q.QFrame.NoFrame);panel=Q.QWidget();self.body=Q.QVBoxLayout(panel);scroll.setWidget(panel);outer.addWidget(scroll,1)
        self.confirm=None
        if confirm:
            self.confirm=Q.QCheckBox('I completed this step in Google');self.confirm.toggled.connect(self.completeChanged);outer.addWidget(self.confirm)
    def text(self,text):
        label=Q.QLabel(text);label.setWordWrap(True);label.setTextFormat(QtCore.Qt.PlainText);label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse);self.body.addWidget(label);return label
    def button(self,text,callback):
        button=Q.QPushButton(text);button.clicked.connect(callback);self.body.addWidget(button);return button
    def isComplete(self):return self.confirm is None or self.confirm.isChecked()
    def finish_layout(self):self.body.addStretch(1)

class YouTubeSetup(Q.QWizard):
    def __init__(self,parent=None,connected=False):
        super().__init__(parent);self.setWindowTitle('Guided YouTube Setup');self.resize(720,690);self.setMinimumSize(530,460);self.setWizardStyle(Q.QWizard.ModernStyle)
        self.setOption(Q.QWizard.NoBackButtonOnStartPage,True);self.connected=connected;self.config_path=ROOT/'Settings/youtube_client.json';self.progress_path=ROOT/'Settings/youtube_setup.json';self.config_file='';self.needs_connect=False
        self.setButtonText(Q.QWizard.NextButton,'Next →');self.setButtonText(Q.QWizard.BackButton,'← Back');self.setButtonText(Q.QWizard.CancelButton,'Close — save my place');self.setButtonText(Q.QWizard.FinishButton,'Connect my YouTube account' if not connected else 'Finish')
        saved=load_json(self.progress_path);self._saved=saved
        self.project=Q.QLineEdit(saved.get('project_id',''));self.project.setPlaceholderText('Optional, for example stereo-slideshow-123456');self.project.setMaxLength(30)
        self.pages=[];self._building=True
        p=self.add_step('Welcome — connect your own YouTube channel','Step 1 of 8 · We will guide you through each Google screen.')
        p.text('This connects only your own YouTube account. Nothing is uploaded during setup. Your Google password is entered only on Google’s website; renewable authorization is kept in your Mac’s Keychain.')
        p.text('There are two places involved:\n• Your browser: Google’s setup pages and sign-in screens.\n• This Stereo Slideshow Mac application: this guide and the final connection button.\n\nUse Command–Tab or the Dock to switch back to this app after each browser step. This guide stays open while you work in the browser.')
        p.text('For this version, you create a Google project and download a small Desktop client JSON file once. The screens below show what to click and what to enter. You may stop and return later. Rendering and music generation do not need this connection.')
        self.resume_button=p.button('Resume where I stopped',lambda:self.jump(self.resume_step));self.resume_step=max(0,min(7,int(saved.get('step',0)))) if str(saved.get('step',0)).isdigit() else 0;self.resume_button.setEnabled(self.resume_step>0)
        p.button('I already downloaded the Google client JSON — skip to connection',lambda:self.jump(7))
        p.button('Open full written guide',self.open_manual)
        p=self.add_step('Create a Google project','Step 2 of 8 · In your browser, open Google Cloud Console.',True)
        p.button('Open Google Cloud Console',lambda:self.open_google('projectcreate'))
        p.text('1. Sign in with the Google account you use for your YouTube channel.\n2. If you see an existing project, click its name near the top, then New Project. The button above may open New Project directly.\n3. Project name: Stereo Slideshow (or a name you prefer).\n4. Parent resource: leave No organization for a personal account.\n5. Click Create. Wait until the project is selected near the top of Google’s page.')
        p.text('A notice saying you have projects remaining is informational. A free-trial banner is separate from creating this project; do not click Start free for this guide. If the project name is already in use on your account, choose a distinguishable name.')
        p.text('Optional: enter the Project ID shown on Google’s dashboard. It can differ from the project name. This lets later buttons open the correct project directly. If left blank, check the project name near the top of each Google page yourself.')
        p.body.addWidget(self.project);self.project_hint=p.text('');self.project.textChanged.connect(self.project_changed)
        p=self.add_step('Enable the YouTube service','Step 3 of 8 · In Google Cloud, use APIs & Services → Library.',True)
        p.button('Open YouTube Data API v3',lambda:self.open_google('apis/library/youtube.googleapis.com'))
        p.text('1. Check that your Stereo Slideshow project is selected at the top.\n2. Open APIs & Services → Library if needed.\n3. Search for YouTube Data API v3 and select it.\n4. Click Enable.\n\nYou are finished when the page says Status: Enabled, or shows a Disable API button. Do not click Disable API. Return to this app, check the box below and choose Next.')
        p=self.add_step('Set up the Google permission screen','Step 4 of 8 · Configure the app name, audience and contact email.',True)
        p.button('Open Google Auth setup',lambda:self.open_google('auth/overview'))
        p.button('Copy app name: Stereo Slideshow',lambda:self.copy('Stereo Slideshow'))
        p.text('1. From APIs & Services, choose OAuth consent screen, or use the button above.\n2. If shown, click Get started.\n3. App Information: enter Stereo Slideshow as the app name. Choose your own address under User support email. Click Next.\n4. Audience: choose External, then Next. External allows personal Google accounts; it does not publish your videos.\n5. Contact Information: enter your own email and click Next.\n6. Finish: review Google’s agreement, accept if you agree, then click Create.')
        p.text('If you already see OAuth Overview with Branding, Audience, Clients and Data Access in the left sidebar, this initial configuration is already created. Leave the app in Testing for this personal setup; publishing the Google app is a separate developer task.')
        p=self.add_step('Allow your Google account to test the connection','Step 5 of 8 · Google Auth Platform → Audience.',True)
        p.button('Open Audience and test users',lambda:self.open_google('auth/audience'))
        p.text('1. Check the selected project near the top of Google’s page.\n2. Click Audience in the left sidebar.\n3. Scroll to Test users.\n4. Click Add users.\n5. Enter the Google email address you use to sign into the YouTube channel.\n6. Click Save.\n\nYour email should appear in the test-user list. A count of 1 test user is normal when you added only yourself. Leave Publishing status as Testing for now.')
        p.text('For a Brand Account channel, add the Google account used to sign in, not the channel’s display name. Google may offer the channel choice later during connection. This guide does not ask you to enter or save your email here.')
        p=self.add_step('Choose the two YouTube permissions','Step 6 of 8 · Google Auth Platform → Data Access.',True)
        p.button('Open Data Access',lambda:self.open_google('auth/scopes'))
        p.button('Copy both required permission addresses',lambda:self.copy('\n'.join(SCOPES)))
        scopes=Q.QPlainTextEdit('\n'.join(SCOPES));scopes.setReadOnly(True);scopes.setFixedHeight(85);p.body.addWidget(scopes)
        p.text('1. Click Add or remove scopes. A panel opens on the right.\n2. Scroll down inside that panel to Manually add scopes.\n3. Click Copy both required permission addresses above and paste into its text box. Keep one address per line.\n4. Click Add to table.\n5. Click Update at the bottom of the panel.\n6. Back on Data Access, the two rows should end in youtube.upload and youtube.readonly. If a Save button is shown, click it. Some Google screens save when you click Update.')
        p.text('youtube.upload is used to upload videos. youtube.readonly lets the app identify the destination channel. Do not add unrelated permissions. The table may classify these as Sensitive; that is Google’s classification and is expected for these permissions.')
        p=self.add_step('Create and download the Desktop connection file','Step 7 of 8 · Google Auth Platform → Clients.',True)
        p.button('Open Clients',lambda:self.open_google('auth/clients'))
        p.text('1. Click Create client (or Create OAuth client).\n2. Application type: choose Desktop app. Do not choose Web application.\n3. Name: Stereo Slideshow.\n4. Leave any optional AI-powered-agent option unchecked; this is a desktop uploader.\n5. Click Create.\n6. In the OAuth client created pop-up, click Download JSON BEFORE closing it. Google may not let you download that client secret again later.\n7. Save the file in Downloads. It often begins client_secret_ and ends .json.\n8. After the download finishes, you may close the Google pop-up.')
        p.text('Keep this file on your own Mac. Do not post its contents or a screenshot of its secret on GitHub. The app will import it locally. If you closed the pop-up without downloading and Google no longer offers Download JSON, create another Desktop client and download it before closing; do not delete a client you are already using.')
        p=self.add_step('Return to this Mac app and connect','Step 8 of 8 · The next file button is here, inside Stereo Slideshow.')
        p.text('You are now back in the actual Stereo Slideshow Mac application. Names saying Stereo Slideshow on Google’s website are project/client names, not this app’s buttons.')
        self.file_label=p.text('No connection file selected yet.');self.file_button=p.button('Choose the JSON I downloaded…',self.pick_json);self.file_error=p.text('')
        p.text('After choosing the file, click Connect my YouTube account below. Google will open in your browser:\n1. Choose the Google account you added as a test user, and the intended channel if offered.\n2. If Google shows a testing/unverified notice, verify it names the app/project you created; review the notice before continuing.\n3. At “Select what Stereo Slideshow can access,” check both Manage your YouTube videos and View your YouTube account (or Select all when those are the only two).\n4. Click Continue.\n5. When told to return, use Command–Tab or the Dock to switch back to the Stereo Slideshow app. Check the connected channel name at the top of its YouTube window.')
        p.text('Nothing is uploaded by connecting. For your first video, keep Visibility set to Private, choose your finished SBS file, review the other fields, then use Upload to YouTube.')
        if connected:p.text('An account is already connected. You may finish this guide without changing it. To switch channels later, use Connect / change channel in the uploader.')
        p.text('If Google says access is blocked: check the test-user email, both permissions, enabled YouTube API and Desktop client type. If sign-in times out, start Connect again in the app. If your browser has a connection error at 127.0.0.1, the sign-in attempt may have expired; return to the app and retry. Testing connections may need renewal after seven days.')
        self.status=Q.QLabel('');self.status.setWordWrap(True);self.status.setTextFormat(QtCore.Qt.PlainText)
        self.setSideWidget(None)
        for p in self.pages:p.finish_layout()
        for i,p in enumerate(self.pages):
            if p.confirm:p.confirm.setChecked(str(i) in saved.get('completed',[]))
        try:client_config(self.config_path);self.config_file=str(self.config_path);self.file_label.setText('A Desktop client is already saved in this app. You can use it, or choose another file. No client secret is displayed.')
        except Exception:pass
        self.currentIdChanged.connect(self.step_changed);self.project_changed();self._building=False
        from ui_controls import protect_settings_wheel
        protect_settings_wheel(self)
        if parent and hasattr(parent,'parent') and hasattr(parent.parent(),'shortcuts'):parent.parent().shortcuts.bind(self,'close',self.reject)
    def add_step(self,title,subtitle,confirm=False):
        page=SetupPage(title,subtitle,confirm,self);self.pages.append(page);self.addPage(page);return page
    def jump(self,step):self.setStartId(step);self.restart()
    def project_changed(self,*args):
        value=self.project.text().strip()
        self.project_hint.setText('Project ID format looks valid.' if re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]',value) else 'Leave this blank if you are unsure; later pages still work.' if value else '')
    def open_google(self,path):
        project=self.project.text().strip();url='https://console.cloud.google.com/'+path
        if re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]',project):url+='?'+urlencode({'project':project})
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):Q.QMessageBox.information(self,'Open Google page','Could not open your default browser. Open console.cloud.google.com in your browser and follow this step’s instructions.')
    def open_manual(self):
        url=QtCore.QUrl.fromLocalFile(str(ROOT/'Development/User_Guide.html'));url.setFragment('youtube');QtGui.QDesktopServices.openUrl(url)
    def copy(self,value):Q.QApplication.clipboard().setText(value)
    def pick_json(self):
        path,_=Q.QFileDialog.getOpenFileName(self,'Choose the Google Desktop client JSON you downloaded',str(Path.home()/'Downloads'),'JSON files (*.json)')
        if not path:return
        try:client_config(path)
        except Exception as error:self.file_error.setText(str(error));return
        self.config_file=path;self.file_label.setText('Selected: '+Path(path).name);self.file_error.setText('Ready. Use the Connect button below when you are ready to sign in.')
    def save_progress(self):
        completed=[str(i) for i,p in enumerate(self.pages) if p.confirm and p.confirm.isChecked()]
        try:atomic_json(self.progress_path,{'step':self.resume_step if self.currentId()<=0 else self.currentId(),'completed':completed,'project_id':self.project.text().strip()})
        except OSError:return False
        return True
    def step_changed(self,step):
        if not self._building:
            if step>0:self.resume_step=step
            self.save_progress()
    def accept(self):
        if self.connected:self.needs_connect=False
        else:
            try:client_config(self.config_file)
            except Exception:self.file_error.setText('First click Choose the JSON I downloaded… and select your Desktop client file.');return
            self.needs_connect=True
        self.save_progress();super().accept()
    def reject(self):self.save_progress();super().reject()
    def closeEvent(self,event):self.save_progress();event.accept()
