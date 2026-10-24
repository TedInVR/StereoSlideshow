"""Acquire the maintenance lock before loading any GUI application source."""
import os,runpy
from pathlib import Path
from maintenance_lock import app_start_guard

def main():
    root=Path(os.environ.get('STEREO_SLIDESHOW_HOME',str(Path(__file__).resolve().parent.parent)))
    guard=app_start_guard(root)
    try:runpy.run_path(str(root/'Development/app.py'),run_name='__main__')
    finally:
        if guard:guard.release()

if __name__=='__main__':main()
