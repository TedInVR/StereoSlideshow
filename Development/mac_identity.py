"""Set the Python-hosted app's Cocoa name before Qt initializes native menus.

Only process-local names are changed; the system Python bundle is never edited.
Uses macOS Foundation directly, without an additional Python dependency.
"""
import ctypes
import sys

NAME='Stereo Slideshow'

class CocoaIdentity:
    def __init__(self):
        p=ctypes.c_void_p
        self.foundation=ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
        self.objc=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        self.cf=ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.objc.objc_getClass.argtypes=[ctypes.c_char_p];self.objc.objc_getClass.restype=p
        self.objc.sel_registerName.argtypes=[ctypes.c_char_p];self.objc.sel_registerName.restype=p
        self.send=ctypes.CFUNCTYPE(p,p,p)(('objc_msgSend',self.objc))
        self.set_one=ctypes.CFUNCTYPE(None,p,p,p)(('objc_msgSend',self.objc))
        self.set_two=ctypes.CFUNCTYPE(None,p,p,p,p)(('objc_msgSend',self.objc))
        self.is_kind=ctypes.CFUNCTYPE(ctypes.c_bool,p,p,p)(('objc_msgSend',self.objc))
        self.cf.CFStringCreateWithCString.argtypes=[p,ctypes.c_char_p,ctypes.c_uint32];self.cf.CFStringCreateWithCString.restype=p
        self.cf.CFRelease.argtypes=[p];self.cf.CFRelease.restype=None
    def selector(self,value):return self.objc.sel_registerName(value.encode())
    def object(self,class_name,method):return self.send(self.objc.objc_getClass(class_name.encode()),self.selector(method))
    def string(self,value):
        result=self.cf.CFStringCreateWithCString(None,value.encode('utf-8'),0x08000100)
        if not result:raise RuntimeError('Could not create the macOS application name.')
        return result
    def set_name(self,name):
        value=self.string(name)
        try:
            process=self.object('NSProcessInfo','processInfo')
            self.set_one(process,self.selector('setProcessName:'),value)
            bundle=self.object('NSBundle','mainBundle');changed=False
            # Qt obtains its native menu name from the main bundle, which may be
            # Python.app when launched through a framework Python interpreter.
            for method in ['infoDictionary','localizedInfoDictionary']:
                dictionary=self.send(bundle,self.selector(method))
                mutable=self.objc.objc_getClass(b'NSMutableDictionary')
                if dictionary and self.is_kind(dictionary,self.selector('isKindOfClass:'),mutable):
                    for field in ['CFBundleName','CFBundleDisplayName']:
                        key=self.string(field)
                        try:self.set_two(dictionary,self.selector('setObject:forKey:'),value,key)
                        finally:self.cf.CFRelease(key)
                    if method=='infoDictionary':changed=True
            return changed
        finally:self.cf.CFRelease(value)

def configure_macos_identity(bridge=None):
    if sys.platform!='darwin':return False
    try:return (bridge or CocoaIdentity()).set_name(NAME)
    except Exception as error:
        # Naming failure must not stop rendering or prevent the application opening.
        print('macOS application naming could not be applied: '+str(error),file=sys.stderr)
        return False
