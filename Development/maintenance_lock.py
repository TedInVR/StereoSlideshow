"""Coordinate app startup and unattended installation across processes."""
import json,os,sys,time
from pathlib import Path

class MaintenanceLock:
    def __init__(self,root):
        self.root=Path(root);self.handle=None
    def acquire(self,role):
        directory=self.root/'Runtime';directory.mkdir(parents=True,exist_ok=True)
        handle=(directory/'maintenance.lock').open('a+b')
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b' ');handle.flush()
        handle.seek(0)
        try:
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:handle.close();return False
        self.handle=handle
        status=directory/'maintenance_status.json';temporary=status.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(pid=os.getpid(),role=role)));os.replace(temporary,status)
        return True
    def release(self):
        if self.handle:
            if sys.platform=='win32':
                import msvcrt
                self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
            self.handle.close();self.handle=None

def app_start_guard(root):
    guard=MaintenanceLock(root)
    if guard.acquire('app'):return guard
    try:role=json.loads((Path(root)/'Runtime/maintenance_status.json').read_text()).get('role')
    except (OSError,ValueError):role=None
    # A second process must not import GUI modules while installation may start.
    # The original application remains open; no second instance is needed.
    if role=='app':raise SystemExit(0)
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        time.sleep(.2)
        if guard.acquire('app'):
            guard.release()
            # The entry-point code was loaded before the wait. Execute it fresh.
            script=Path(root)/'Development/windows_launch.py' if sys.platform=='win32' else Path(root)/'Development/app_bootstrap.py'
            os.execv(sys.executable,[sys.executable,str(script)]+sys.argv[1:])
    raise RuntimeError('An update is still being installed. Try opening Stereo Slideshow again shortly.')
