"""Plain-language audience guidance, with the creator retaining the choice."""
from PySide6 import QtCore,QtWidgets as Q

CHOICES=[('Choose the intended audience…',None),
 ('No — general audience',False),
 ('Yes — content directed at children',True)]
HINT='This asks who you made the video for, not whether children could watch it. For a general-audience slideshow not aimed at children, choose No.'
DETAILS='''<h2>Who did you make this video for?</h2>
<p>YouTube requires an audience classification. This is about the people the video targets, rather than a rating of whether it is safe for children.</p>
<h3>No — general audience</h3>
<p>Choose this for videos intended for general viewers, teens or adults, without specifically targeting children. A travel slideshow or photography presentation made for general viewers can fit here even when it is family-friendly.</p>
<p>“Not made for kids” does not mean adults-only. It also does not guarantee suitability for every age; age restrictions are a separate issue.</p>
<h3>Yes — content directed at children</h3>
<p>Choose this for child-directed content, such as preschool lessons or nursery songs. In the U.S., this concerns children under 13; relevant ages can differ elsewhere. Children do not have to be the primary audience: a video deliberately targeting children alongside older viewers may also belong here. Consider YouTube’s audience factors for borderline cases.</p>
<h3>What changes on YouTube?</h3>
<p>Made-for-kids videos lose features including comments, live chat, notifications and saving to playlists or Watch Later. Personalized advertising is disabled; contextual ads may still appear. Choosing No does not guarantee comments, ads or monetization—other channel settings, eligibility requirements and policies still apply.</p>
<p>Choose the classification that matches the video’s intended audience. This app leaves that decision to you.</p>
<p><a href="https://support.google.com/youtube/answer/9528076?hl=en">YouTube: deciding whether content is made for kids</a><br>
<a href="https://support.google.com/youtube/answer/9527654?hl=en">YouTube: audience settings and affected features</a><br>
<a href="https://support.google.com/youtube/answer/9713557?hl=en">YouTube: ads on made-for-kids content</a></p>'''

def audience_hint(value):
    if value is None:return HINT
    if value is False:return 'Selected: not directed at children. This does not mean adults-only. Comments and monetization still depend on your settings and YouTube’s other rules.'
    return 'Selected: directed at children. YouTube disables comments and several other features. Personalized ads are disabled, but other ads may still run.'

def show_audience_help(parent):
    dialog=Q.QDialog(parent);dialog.setWindowTitle('YouTube audience — what does this mean?');dialog.resize(640,570)
    layout=Q.QVBoxLayout(dialog);text=Q.QTextBrowser();text.setOpenExternalLinks(True);text.setHtml(DETAILS);layout.addWidget(text)
    buttons=Q.QDialogButtonBox(Q.QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    close=buttons.button(Q.QDialogButtonBox.Close);close.setDefault(True);close.setFocus()
    from PySide6.QtGui import QShortcut,QKeySequence
    manager=getattr(parent,'shortcuts',None) or getattr(parent.parent(),'shortcuts',None)
    if manager:manager.bind(dialog,'close',dialog.reject)
    else:
        shortcut=QShortcut(QKeySequence('Ctrl+W'),dialog);shortcut.activated.connect(dialog.reject)
    dialog.exec()
