"""Experimental per-user Windows source installation; no admin privileges needed."""
import json,os,shutil,subprocess,sys
from pathlib import Path
from install_support import verify_package,recognized,install_payload,ensure_runtime,check_running
from platform_support import runtime_python,reopen

def install(package,target):
    manifest=verify_package(package)
    if target.exists() and not recognized(target):raise RuntimeError('The destination is not a recognized Stereo Slideshow installation.')
    check_running(target,Path.home());install_payload(package,target,manifest);ensure_runtime(target,Path.home())
    # Refresh declared dependencies even when an earlier runtime was already usable.
    subprocess.run([str(runtime_python(target)),'-m','pip','install','-r',str(target/'Development/requirements.txt')],check=True)
    icon=target/'Runtime/StereoSlideshow.ico'
    subprocess.run([str(runtime_python(target)),'-c',"from PIL import Image;import sys;Image.open(sys.argv[1]).save(sys.argv[2],format='ICO',sizes=[(16,16),(32,32),(48,48),(256,256)])",str(target/'Stereo Slideshow.app/Contents/Resources/StereoSlideshow.png'),str(icon)],check=True)
    env=dict(os.environ,STEREO_SLIDESHOW_HOME=str(target))
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(target/'Development/windows_shortcuts.ps1')],env=env,check=True)

def main():
    if sys.platform!='win32':raise RuntimeError('Run this installer on Windows.')
    if not (3,10)<=sys.version_info[:2]<(3,15):raise RuntimeError('Install 64-bit Python 3.10–3.14 first; Python 3.12 is a conservative choice.')
    if sys.maxsize<=2**32:raise RuntimeError('This experimental package requires 64-bit Python.')
    for name in ['ffmpeg','ffprobe']:
        if not shutil.which(name):raise RuntimeError('Install FFmpeg with ffmpeg.exe and ffprobe.exe available on PATH, then reopen the installer. See Development/WINDOWS_README.md.')
    package=Path(__file__).resolve().parent.parent
    target=Path(os.environ['LOCALAPPDATA'])/'Programs/Stereo Slideshow'
    print('Experimental Windows installation. Not tested on Windows.\nInstalling to:',target)
    install(package,target);print('Ready. Use the Stereo Slideshow (Experimental) desktop shortcut.');reopen(target)

if __name__=='__main__':
    try:main()
    except Exception as error:print('Installation stopped:',error);sys.exit(1)
