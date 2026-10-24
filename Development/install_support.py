"""Install/update one permanent Stereo Slideshow project; no admin prompt required."""
import argparse, hashlib, json, os, plistlib, shutil, subprocess, sys, tempfile, time, zipfile
from pathlib import Path
from platform_support import runtime_python,windows_process_exited,quiet_options
ID='com.ted.stereoslideshow'
NAME='Stereo Slideshow'
MARKER='project.json'

def recognized(root):
    try:return json.loads((root/MARKER).read_text()).get('identifier')==ID
    except (OSError,ValueError):return False

def choose_target(package,home,applications=Path('/Applications')):
    userapps=home/'Applications'
    # An already placed project folder stays where the user put it.
    if package.name==NAME and package.parent in (applications,userapps):return package
    for root in [applications/NAME,userapps/NAME]:
        if recognized(root):return root
    if applications.is_dir() and os.access(applications,os.W_OK):return applications/NAME
    userapps.mkdir(parents=True,exist_ok=True)
    return userapps/NAME

def verify_package(package):
    manifest=json.loads((package/'manifest.json').read_text())
    for relative,expected in manifest['sha256'].items():
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts:raise RuntimeError('Invalid package path.')
        source=package/path
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Package integrity check failed: '+relative+'. Extract a fresh copy of the ZIP.')
    if not recognized(package):raise RuntimeError('This is not a Stereo Slideshow project package.')
    return manifest

def check_running(target,home):
    if sys.platform=='win32':
        try:pid=int(json.loads((target/'Runtime/running.json').read_text())['pid'])
        except (OSError,ValueError,KeyError):return
        if pid>0 and not windows_process_exited(pid):raise RuntimeError('Close Stereo Slideshow before updating.')
        return
    try:
        pid=int(json.loads((target/'Runtime/running.json').read_text())['pid'])
        command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True).strip()
        if str(target/'Development/app.py') in command:raise RuntimeError('Quit Stereo Slideshow before installing this update, then run the installer again.')
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError):pass
    # Also catch the previous packaging while the user migrates from v0.12.
    try:
        commands=subprocess.check_output(['ps','-axo','command='],text=True)
        for line in commands.splitlines():
            if 'Stereo Slideshow.app/Contents/Resources/app.py' in line and str(home) in line:
                raise RuntimeError('The previous Stereo Slideshow app is still open. Quit it before installing, then run the installer again.')
    except (OSError,subprocess.CalledProcessError):pass

def atomic_copy(source,dest):
    if source.resolve()==dest.resolve():return
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_name(dest.name+'.installing')
    shutil.copy2(source,temp);os.replace(temp,dest)

def migrate_settings(target,home):
    destination=target/'Settings/settings.json'
    if destination.exists():return
    legacy=home/'Library/Application Support/Stereo Slideshow/settings.json'
    if legacy.is_file():
        # Validate before copying, but preserve every caption, blank, and option.
        json.loads(legacy.read_text());atomic_copy(legacy,destination)
        print('Carried over existing settings and captions.')

def runtime_ok(python,full=True):
    if not python.exists():return False
    check=("import PIL,PySide6,keyring;from PySide6 import QtWidgets;" if full else "")+"import sys;sys.exit(0 if (3,9)<=sys.version_info[:2]<(3,15) else 1)"
    return subprocess.run([str(python),'-c',check],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def ensure_runtime(target,home):
    env=target/'Runtime/venv';python=runtime_python(target)
    if runtime_ok(python):print('Existing runtime is ready.');return
    if runtime_ok(python,full=False):
        print('Updating app dependencies in the existing runtime…')
        subprocess.run([str(python),'-m','pip','install','-r',str(target/'Development/requirements.txt')],check=True)
        if not runtime_ok(python):raise RuntimeError('The updated runtime could not be verified. Please share the installer output.')
        return
    legacy=home/'Library/Application Support/Stereo Slideshow/venv'
    if sys.platform!='win32' and not env.exists() and runtime_ok(legacy/'bin/python'):
        print('Copying the existing runtime into the permanent folder…')
        shutil.copytree(legacy,env,symlinks=True)
        if runtime_ok(python):return
        shutil.rmtree(env) # Only the newly created, unusable copy is removed.
    print('Preparing the local runtime…')
    subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
    subprocess.run([str(python),'-m','pip','install','-r',str(target/'Development/requirements.txt')],check=True)
    if not runtime_ok(python):raise RuntimeError('The runtime could not be verified. Please share the installer output.')

def backup_previous(target):
    if not (target/'Development').exists():return
    destination=target/'Updates/Previous_Source.zip';destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.installing')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ['Development', 'Stereo Slideshow.app/Contents/Info.plist','project.json','manifest.json']:
            path=target/name
            if path.is_dir():
                for file in path.rglob('*'):
                    if file.is_file() and '__pycache__' not in file.parts:archive.write(file,file.relative_to(target))
            elif path.is_file():archive.write(path,path.relative_to(target))
    os.replace(temporary,destination)

def install_payload(package,target,manifest):
    if target.exists() and package.resolve()!=target.resolve() and not recognized(target):
        raise RuntimeError('The destination already exists but is not a recognized project: '+str(target))
    target.mkdir(parents=True,exist_ok=True)
    if target.resolve()!=package.resolve():backup_previous(target)
    # Keep the app bundle directory and permanent launcher path; replace only payload files.
    for relative in manifest['sha256']:
        atomic_copy(package/relative,target/relative)
    atomic_copy(package/'manifest.json',target/'manifest.json')
    for path in [target/'Install or Update.command',target/'Stereo Slideshow.app/Contents/MacOS/launch']:
        path.chmod(path.stat().st_mode|0o111)
    for cache in (target/'Development').rglob('__pycache__'):
        if cache.is_dir():shutil.rmtree(cache)
    for directory in ['Settings','Logs','Runtime','Updates']:(target/directory).mkdir(exist_ok=True)

def redirect_legacy_launchers(target,home):
    # Preserve old Dock shortcuts without keeping another source tree active.
    # Only modify a launcher whose bundle ID matches this project, and back it up first.
    for legacy in [home/'Applications/Stereo Slideshow.app',Path('/Applications/Stereo Slideshow.app')]:
        if not legacy.is_dir() or legacy.resolve()==(target/'Stereo Slideshow.app').resolve():continue
        try:
            info=plistlib.loads((legacy/'Contents/Info.plist').read_bytes())
            launch=legacy/'Contents/MacOS'/info.get('CFBundleExecutable','launch')
            if info.get('CFBundleIdentifier')!=ID or not os.access(launch,os.W_OK):continue
            backup=target/'Updates/Legacy_Launcher_Backup.zip'
            if not backup.exists():
                with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
                    for f in legacy.rglob('*'):
                        if f.is_file():z.write(f,f.relative_to(legacy.parent))
            # Retain legacy resources as a reversible backup, but route launch to the single project.
            quoted="'"+str(target/'Stereo Slideshow.app').replace("'","'\"'\"'")+"'"
            launch.write_text('#!/bin/bash\nexec /usr/bin/open -a '+quoted+' "$@"\n');launch.chmod(0o755)
            print('An existing app shortcut now opens the permanent app.')
        except (OSError,ValueError,plistlib.InvalidFileException) as e:
            print('Older shortcut was left unchanged:',e)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True);args=parser.parse_args()
    if sys.platform!='darwin':raise RuntimeError('Run this installer on your Mac.')
    package=args.package.resolve();home=Path.home();manifest=verify_package(package)
    for name in ['ffmpeg','ffprobe']:
        if not shutil.which(name):raise RuntimeError(name+' is missing. Install Homebrew FFmpeg, then run the installer again.')
    target=choose_target(package,home);check_running(target,home)
    print('Permanent project folder:',target)
    install_payload(package,target,manifest);migrate_settings(target,home);ensure_runtime(target,home)
    redirect_legacy_launchers(target,home)
    app=target/'Stereo Slideshow.app';os.utime(app,None)
    register=Path('/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister')
    if register.exists():subprocess.run([str(register),'-f',str(app)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('\nReady. Use Stereo Slideshow.app inside this folder.\nFuture updates use the same folder and app icon.\nYou can keep that app in the Dock.')
    subprocess.run(['open','-R',str(app)],check=False)
    subprocess.run(['open',str(app)],check=True)

if __name__=='__main__':
    try:main()
    except Exception as e:print('\nInstallation stopped:',e,file=sys.stderr);sys.exit(1)
