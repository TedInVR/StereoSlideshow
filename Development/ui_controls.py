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


def style_step_section(box,number):
    """Subtle alternating tints that follow the active light/dark palette."""
    from PySide6 import QtGui,QtWidgets
    base=QtWidgets.QApplication.palette().color(QtGui.QPalette.Window)
    accent=QtGui.QColor('#d86673' if number%2 else '#42bdcc')
    amount=.075 if base.lightness()>128 else .12
    tint=QtGui.QColor(*[round(base.getRgb()[i]*(1-amount)+accent.getRgb()[i]*amount) for i in range(3)])
    box.setProperty('stepSection',True)
    box.setStyleSheet('QGroupBox[stepSection="true"] { background-color: '+tint.name()+'; border: 1px solid rgba(128,128,128,45); border-radius: 8px; margin-top: 16px; padding-top: 12px; font-size: 17px; font-weight: 600; } '
        'QGroupBox[stepSection="true"]::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; } '
        'QGroupBox[stepSection="true"] QWidget { font-size: 13px; font-weight: 400; }')
