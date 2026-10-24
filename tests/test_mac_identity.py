"""Platform guard and startup ordering; Cocoa display needs verification on Mac."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import mac_identity as m
class Bridge:
    def __init__(self):self.name=None
    def set_name(self,value):self.name=value;return True
bridge=Bridge()
with patch.object(m.sys,'platform','linux'):
    assert not m.configure_macos_identity(bridge) and bridge.name is None
with patch.object(m.sys,'platform','darwin'):
    assert m.configure_macos_identity(bridge) and bridge.name=='Stereo Slideshow'
    with patch.object(m,'CocoaIdentity',side_effect=OSError('native bridge unavailable')):assert not m.configure_macos_identity()
source=(Path(__file__).resolve().parents[1]/'Development/app.py').read_text()
assert source.index('configure_macos_identity()')<source.index('from PySide6 import')
assert source.index("QtCore.QCoreApplication.setApplicationName('Stereo Slideshow')")<source.index('app=Application(sys.argv)')
print('macOS name: platform guard, bridge dispatch, nonfatal failure and naming before Qt initialization passed. Native menu display requires a Mac check.')
