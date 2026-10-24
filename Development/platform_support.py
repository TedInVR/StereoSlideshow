"""Small OS boundary shared by the app, installer and detached updater."""
import ctypes,os,subprocess,sys
from pathlib import Path

def runtime_python(root,windowed=False):
    return Path(root)/'Runtime/venv'/('Scripts/'+('pythonw.exe' if windowed else 'python.exe') if sys.platform=='win32' else 'bin/python')

def background_options():
    return {'creationflags':0x08000000|0x00000200} if sys.platform=='win32' else {'start_new_session':True}

def quiet_options():return {'creationflags':0x08000000} if sys.platform=='win32' else {}

def windows_process_exited(pid,timeout_ms=0):
    """Never use os.kill(pid, 0) on Windows: it can terminate the process."""
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x00100000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return True
        raise OSError('Could not safely check the running app. Close it before updating.')
    try:
        result=kernel.WaitForSingleObject(handle,timeout_ms)
        if result==0:return True
        if result==258:return False
        raise OSError('Windows could not wait for the app to close.')
    finally:kernel.CloseHandle(handle)

def reopen(root):
    root=Path(root)
    if sys.platform=='darwin':subprocess.run(['/usr/bin/open','-n',str(root/'Stereo Slideshow.app')],check=False)
    elif sys.platform=='win32':
        log=root/'Logs/app.log'
        with log.open('a') as output:subprocess.Popen([str(runtime_python(root,True)),str(root/'Development/windows_launch.py')],stdout=output,stderr=output,**background_options())
