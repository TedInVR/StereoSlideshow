"""Windows branch checks on a non-Windows host; these are not device testing."""
import json,os,sys,tempfile,threading,types
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import platform_support as p,install_support as install,music_generator as music,youtube_upload as youtube,update_apply

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    with patch.object(p.sys,'platform','win32'):
        assert p.runtime_python(root)==root/'Runtime/venv/Scripts/python.exe'
        assert p.runtime_python(root,True)==root/'Runtime/venv/Scripts/pythonw.exe'
        assert p.background_options()['creationflags']&0x08000000
        assert p.quiet_options()['creationflags']==0x08000000
        # Windows updater must use the non-destructive native wait, never os.kill.
        with patch.object(update_apply,'windows_process_exited',return_value=True) as wait,patch.object(update_apply.os,'kill',side_effect=AssertionError('os.kill on Windows')):
            update_apply.wait_for_exit(1234);assert wait.call_args.args[0]==1234
        (root/'Runtime').mkdir();(root/'Runtime/running.json').write_text(json.dumps({'pid':1234}))
        with patch.object(install,'windows_process_exited',return_value=False):
            try:install.check_running(root,root)
            except RuntimeError:pass
            else:raise AssertionError('Running app was not protected')
        fake=types.ModuleType('keyring.backends.Windows');fake.WinVaultKeyring=Mock(return_value='secure Windows backend')
        with patch.dict(sys.modules,{'keyring.backends.Windows':fake}):assert youtube.CredentialStore()._keyring()=='secure Windows backend'
        (root/'Logs').mkdir();(root/'Development').mkdir()
        with patch.object(p.subprocess,'Popen') as popen:
            p.reopen(root);assert popen.call_args.args[0][0].endswith('Scripts/pythonw.exe')
    ace=root/'ACE-Step';(ace/'acestep').mkdir(parents=True);(ace/'acestep/api_server.py').write_text('')
    python=ace/'.venv/Scripts/python.exe';python.parent.mkdir(parents=True);python.write_text('placeholder');python.chmod(0o755)
    with patch.object(music.platform,'system',return_value='Windows'):
        folder,command=music.launch_command(ace,8001);assert command[0]==str(python) and command[1:3]==['-m','acestep.api_server']
        server=music.LocalServer();server.process=Mock();server.process.poll.return_value=None
        with patch.object(music.os,'killpg',side_effect=AssertionError('POSIX process kill on Windows')):server.stop()
        server.process.terminate.assert_called_once()
source=Path(__file__).resolve().parents[1]/'Development'
assert 'EXPERIMENTAL' in (source/'Install-Windows.cmd').read_text()
assert 'UNTESTED' in (source/'WINDOWS_README.md').read_text()
assert 'pythonw.exe' in (source/'windows_shortcuts.ps1').read_text()
print('Windows simulated branches: runtime paths, hidden child processes, safe updater wait, running-app guard, secure-backend selection, restart and ACE-Step launch/stop passed. No actual Windows execution verified.')
