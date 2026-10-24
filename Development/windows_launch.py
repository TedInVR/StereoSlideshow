"""Windowed Windows entry point with persistent diagnostics."""
import ctypes,os,runpy,sys,traceback
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent.parent;os.environ['STEREO_SLIDESHOW_HOME']=str(root)
    logs=root/'Logs';logs.mkdir(exist_ok=True)
    with (logs/'app.log').open('a',encoding='utf-8') as log:
        sys.stdout=log;sys.stderr=log;sys.path.insert(0,str(root/'Development'))
        try:runpy.run_path(str(root/'Development/app_bootstrap.py'),run_name='__main__')
        except SystemExit as error:
            if error.code:raise
        except Exception:
            traceback.print_exc();log.flush()
            ctypes.windll.user32.MessageBoxW(None,'Stereo Slideshow could not start. See '+str(logs/'app.log'),'Stereo Slideshow — experimental Windows version',0x10)
            return 1
    return 0

if __name__=='__main__':sys.exit(main())
