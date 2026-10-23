"""Keep wheel gestures on settings panes from editing control values."""
from PySide6 import QtCore, QtGui, QtWidgets as Q
class SettingsWheelFilter(QtCore.QObject):
    def eventFilter(self,control,event):
        if event.type()!=QtCore.QEvent.Wheel:return False
        ancestor=control.parentWidget()
        while ancestor is not None and not isinstance(ancestor,Q.QScrollArea):ancestor=ancestor.parentWidget()
        if ancestor is not None:
            viewport=ancestor.viewport()
            forwarded=QtGui.QWheelEvent(QtCore.QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint())),event.globalPosition(),event.pixelDelta(),event.angleDelta(),event.buttons(),event.modifiers(),event.phase(),event.inverted(),event.source())
            Q.QApplication.sendEvent(viewport,forwarded)
        event.accept();return True

def protect_settings_wheel(root):
    filter=SettingsWheelFilter(root)
    for control in root.findChildren(Q.QComboBox)+root.findChildren(Q.QAbstractSpinBox):
        control.installEventFilter(filter)
    root.settings_wheel_filter=filter

class TimingSummary(Q.QPlainTextEdit):
    """Give calculation text its own readable, scrollable space on every style."""
    def __init__(self,text='',parent=None):
        super().__init__(parent)
        self.setReadOnly(True);self.setLineWrapMode(Q.QPlainTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setAccessibleName('Timing summary')
        self.setToolTip('Slideshow timing summary. Scroll inside this box if there are more lines; text can be selected and copied.')
        self.fit_height();self.setPlainText(text)
    def fit_height(self):self.setFixedHeight(max(160,self.fontMetrics().lineSpacing()*8+18))
    def setText(self,text):self.setPlainText(text)
    def text(self):return self.toPlainText()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.FontChange,QtCore.QEvent.StyleChange):self.fit_height()
