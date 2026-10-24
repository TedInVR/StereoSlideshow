"""Unattended update decisions, cross-process exclusion and agent configuration."""
import json,os,plistlib,shutil,subprocess,sys,tempfile,threading,time
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import automatic_updates as auto,background_update as bg,maintenance_lock as locks

with tempfile.TemporaryDirectory() as td:
    root=Path(td)/'Stereo Slideshow';root.mkdir();(root/'project.json').write_text(json.dumps(dict(identifier='com.ted.stereoslideshow',version='1.0')))
    assert auto.enabled(root);auto.set_enabled(root,False);assert not auto.enabled(root)
    with patch.object(bg,'check_update',side_effect=AssertionError('Disabled updater used network')):assert bg.update_once(root)=='disabled'
    auto.set_enabled(root,True)
    with patch.object(bg,'check_running',side_effect=RuntimeError('App open')),patch.object(bg,'check_update',side_effect=AssertionError('Open app used network')):assert bg.update_once(root)=='app running'
    release=dict(version='2.0',sha='a'*40,available=True);job=root/'Updates/download-test';(job/'payload').mkdir(parents=True)
    result=dict(package=str(job/'payload'),job=str(job),version='2.0');calls=[]
    with patch.object(bg,'check_running',return_value=None),patch.object(bg,'check_update',return_value=release),patch.object(bg,'stage_update',return_value=result),patch.object(bg,'apply_update',lambda package,target:calls.append((package,target))):
        assert bg.update_once(root)=='updated to 2.0'
    assert len(calls)==1 and not job.exists() and json.loads((root/'Runtime/last_automatic_update.json').read_text())['version']=='2.0'
    # A running app's maintenance lock blocks installation, even if its PID file
    # has not yet been written. This also covers opening the app during download.
    app_lock=locks.MaintenanceLock(root);assert app_lock.acquire('app')
    (job/'payload').mkdir(parents=True)
    with patch.object(bg,'check_running',return_value=None),patch.object(bg,'check_update',return_value=release),patch.object(bg,'stage_update',return_value=result),patch.object(bg,'apply_update',side_effect=AssertionError('Modified running app')):
        assert bg.update_once(root)=='app running'
    assert not job.exists();app_lock.release()
    # A genuinely separate process sees the maintenance lock and cannot acquire it.
    owner=locks.MaintenanceLock(root);assert owner.acquire('update')
    code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from maintenance_lock import MaintenanceLock;g=MaintenanceLock(Path(sys.argv[2]));assert not g.acquire('app')"
    subprocess.run([sys.executable,'-c',code,str(Path(locks.__file__).parent),str(root)],check=True)
    owner.release();other=locks.MaintenanceLock(root);assert other.acquire('app');other.release()
    # Real bootstrap waits outside the GUI source and starts the newly installed code.
    dev=root/'Development';dev.mkdir()
    for name in ['app_bootstrap.py','maintenance_lock.py']:shutil.copyfile(Path(locks.__file__).parent/name,dev/name)
    marker=root/'Runtime/started.txt'
    (dev/'app.py').write_text("from pathlib import Path;Path("+repr(str(marker))+").write_text('old')")
    assert owner.acquire('update')
    child=subprocess.Popen([sys.executable,str(dev/'app_bootstrap.py')],env=dict(os.environ,STEREO_SLIDESHOW_HOME=str(root)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    time.sleep(.3);assert child.poll() is None and not marker.exists()
    (dev/'app.py').write_text("from pathlib import Path;Path("+repr(str(marker))+").write_text('fresh')")
    owner.release();out,err=child.communicate(timeout=8);assert child.returncode==0,err
    assert marker.read_text()=='fresh'
    # No downgrade if a newer manual update arrived while downloading.
    (job/'payload').mkdir(parents=True);(root/'project.json').write_text(json.dumps(dict(identifier='com.ted.stereoslideshow',version='3.0')))
    with patch.object(bg,'check_running',return_value=None),patch.object(bg,'check_update',return_value=release),patch.object(bg,'stage_update',return_value=result),patch.object(bg,'apply_update',side_effect=AssertionError('Downgrade')):assert bg.update_once(root)=='up to date'
    assert not job.exists()
    agent=auto.agent_plist(root);assert agent['StartInterval']==900 and agent['RunAtLoad'] and '--root' in agent['ProgramArguments']
    assert 'background_update.py' in agent['ProgramArguments'][1]
    xml=auto.windows_task_xml(root).decode('utf-16');assert 'InteractiveToken' in xml and 'LeastPrivilege' in xml and 'PT15M' in xml and 'IgnoreNew' in xml
    # Registration commands use the current user's session, never an admin service.
    with patch.object(auto.sys,'platform','darwin'),patch.object(auto.Path,'home',return_value=Path(td)),patch.object(auto.os,'getuid',return_value=501),patch.object(auto.subprocess,'run',return_value=Mock(returncode=1)) as run:
        auto.register(root)
        assert any('bootstrap' in call.args[0] for call in run.call_args_list)
        plist=Path(td)/'Library/LaunchAgents'/(auto.LABEL+'.plist');assert plistlib.loads(plist.read_bytes())['ProgramArguments']==agent['ProgramArguments']
print('Automatic updates: disabled/running-app skips, idle installation, cleanup, no downgrade, cross-process lock, user agent/task configuration and registration commands passed. OS scheduling needs device verification.')
