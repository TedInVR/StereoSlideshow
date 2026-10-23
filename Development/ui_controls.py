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
