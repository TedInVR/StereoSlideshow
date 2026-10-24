"""Scheduled update check/install. Never closes, starts or kills the GUI app."""
import argparse,json,shutil,signal,threading,traceback
from pathlib import Path
from automatic_updates import enabled
from install_support import check_running,recognized
from maintenance_lock import MaintenanceLock
from update_core import check_update,stage_update,version
from update_apply import apply_update

def update_once(root):
    root=Path(root).resolve()
    if not recognized(root) or not enabled(root):return 'disabled'
    try:check_running(root,Path.home())
    except RuntimeError:return 'app running'
    current=json.loads((root/'project.json').read_text())['version'];cancel=threading.Event()
    release=check_update(current,cancel)
    if not release['available']:return 'up to date'
    download=stage_update(root,release,cancel);guard=MaintenanceLock(root)
    try:
        if not enabled(root):return 'disabled'
        if not guard.acquire('update'):return 'app running'
        try:check_running(root,Path.home())
        except RuntimeError:return 'app running'
        if version(json.loads((root/'project.json').read_text())['version'])>=version(release['version']):return 'up to date'
        apply_update(Path(download['package']),root)
        (root/'Runtime/last_automatic_update.json').write_text(json.dumps(dict(version=release['version'])))
        return 'updated to '+release['version']
    finally:
        guard.release();shutil.rmtree(download['job'],ignore_errors=True)

def main():
    def stop(signum,frame):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path);args=parser.parse_args()
    log=args.root/'Logs/automatic_updates.log';log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('a',encoding='utf-8') as output:
        try:print(update_once(args.root),file=output)
        except Exception:traceback.print_exc(file=output)

if __name__=='__main__':main()
