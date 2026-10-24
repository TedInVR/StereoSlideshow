"""Detached updater: wait for app exit, preserve data, roll back failed copies."""
import argparse,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from install_support import recognized,install_payload,atomic_copy,ensure_runtime,check_running
from update_core import validate

def apply_update(package,target):
    package=Path(package).resolve();target=Path(target).resolve()
    if not recognized(target):raise RuntimeError('The installed app folder could not be recognized.')
    check_running(target,Path.home())
    manifest=validate(package);names=list(manifest['sha256'])+['manifest.json']
    for name in names:
        destination=target/name
        if not destination.resolve().is_relative_to(target) or destination.is_symlink():raise RuntimeError('A program path points outside the app folder.')
    # Capture exactly the files we may overwrite, including newly introduced paths.
    with tempfile.TemporaryDirectory(prefix='rollback-',dir=target/'Updates') as td:
        backup=Path(td);existing=[];new=[]
        for name in names:
            dest=target/name
            if dest.exists():atomic_copy(dest,backup/name);existing.append(name)
            else:new.append(name)
        try:
            old_requirements=target/'Development/requirements.txt'
            if not old_requirements.exists() or old_requirements.read_bytes()!=(package/'Development/requirements.txt').read_bytes():
                python=target/'Runtime/venv/bin/python'
                subprocess.run([str(python),'-m','pip','install','-r',str(package/'Development/requirements.txt')],check=True)
            install_payload(package,target,manifest);ensure_runtime(target,Path.home());validate(target)
        except BaseException:
            for name in existing:atomic_copy(backup/name,target/name)
            for name in new:
                if (target/name).is_file():(target/name).unlink()
            raise
    os.utime(target/'Stereo Slideshow.app',None)

def wait_for_exit(pid,timeout=120):
    if pid<=1:raise RuntimeError('Invalid app process identifier.')
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:os.kill(pid,0)
        except ProcessLookupError:return
        time.sleep(.2)
    raise RuntimeError('Stereo Slideshow did not close. No program files were changed. Try updating again.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,required=True);parser.add_argument('--package',type=Path,required=True);parser.add_argument('--pid',type=int,required=True);args=parser.parse_args()
    job=args.package.parent
    if job.parent.resolve()!=(args.target/'Updates').resolve() or not job.name.startswith('download-') or args.package.name!='payload':raise RuntimeError('Unexpected update staging folder.')
    success=False;exited=False
    try:
        wait_for_exit(args.pid);exited=True
        apply_update(args.package,args.target);success=True
        print('Update installed successfully.',flush=True)
    except Exception as error:
        message='Stereo Slideshow could not finish updating. '+str(error)[:350]+'\nDetails: '+str(args.target/'Logs/update.log')
        print(message,flush=True)
        if sys.platform=='darwin':subprocess.run(['/usr/bin/osascript','-e','on run argv','-e','display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "Stereo Slideshow update"','-e','end run',message],check=False)
    finally:
        shutil.rmtree(job,ignore_errors=True)
    # Reopen the new version, or the restored previous version after a failed update.
    if exited and sys.platform=='darwin':subprocess.run(['/usr/bin/open','-n',str(args.target/'Stereo Slideshow.app')],check=False)
    return 0 if success else 1

if __name__=='__main__':sys.exit(main())
