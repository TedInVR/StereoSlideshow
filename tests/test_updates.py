"""Updater transport, archive boundaries, data preservation and rollback."""
import hashlib,json,shutil,sys,tempfile,threading,zipfile,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import update_core as u,update_apply as a

def fixture(root,version,text):
    files={'Development/app.py':text,'Development/requirements.txt':'','Install or Update.command':'echo install','Stereo Slideshow.app/Contents/MacOS/launch':'launch','project.json':json.dumps(dict(identifier=u.ID,version=version))}
    for name,value in files.items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
    manifest=dict(version=version,sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files})
    (root/'manifest.json').write_text(json.dumps(manifest));return manifest

assert u.version('0.29')>u.version('0.28') and u.version('1.2')==u.version('1.2.0')
for url in ['http://api.github.com/test','https://evil.example/test','https://user@github.com/test']:
    try:u.safe_url(url)
    except ValueError:pass
    else:raise AssertionError('Unsafe URL accepted')
cancel=threading.Event();sha='a'*40
with patch.object(u,'read_json',side_effect=[{'sha':sha},{'identifier':u.ID,'version':'0.29'}]) as read:
    assert u.check_update('0.28',cancel)==dict(sha=sha,version='0.29',available=True)
    assert sha in read.call_args_list[1].args[0]
with tempfile.TemporaryDirectory() as td:
    root=Path(td);source=root/'source';source.mkdir();fixture(source,'0.29','new')
    target=root/'installed';target.mkdir();fixture(target,'0.28','old');(target/'Updates').mkdir();(target/'Settings').mkdir();private=target/'Settings/personal.json';private.write_text('keep private')
    archive=root/'release.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for p in source.rglob('*'):
            if p.is_file():z.write(p,'repository-commit/'+str(p.relative_to(source)))
    urls=[]
    def fetch(url,destination,*args,**kwargs):urls.append(url);shutil.copyfile(archive,destination)
    with patch.object(u,'fetch',fetch):download=u.stage_update(target,dict(sha=sha,version='0.29'),cancel)
    assert sha in urls[0] and u.validate(Path(download['package']))['version']=='0.29'
    inode=(target/'Stereo Slideshow.app').stat().st_ino
    with patch.object(a,'ensure_runtime',lambda *args:None):a.apply_update(Path(download['package']),target)
    assert (target/'Development/app.py').read_text()=='new' and private.read_text()=='keep private'
    assert (target/'Stereo Slideshow.app').stat().st_ino==inode and (target/'Updates/Previous_Source.zip').is_file()
    # A failure after a partial write restores every previous program file.
    fixture(target,'0.28','old')
    def fail(package,dest,manifest):
        (dest/'Development/app.py').write_text('half copied');raise OSError('simulated interrupted installation')
    with patch.object(a,'install_payload',fail):
        try:a.apply_update(Path(download['package']),target)
        except OSError:pass
        else:raise AssertionError('Failure not reported')
    assert (target/'Development/app.py').read_text()=='old' and json.loads((target/'project.json').read_text())['version']=='0.28'
    assert private.read_text()=='keep private' and not list((target/'Updates').glob('rollback-*'))
    # Checksum corruption is rejected before installation.
    (Path(download['package'])/'Development/app.py').write_text('corrupt')
    try:u.validate(Path(download['package']))
    except RuntimeError:pass
    else:raise AssertionError('Corrupt file accepted')
    shutil.rmtree(download['job'])
    # Traversal archives and private-data destinations are rejected and cleaned up.
    for bad in ['../escape.txt','repository/../../escape.txt','repository/Settings/personal.json']:
        with zipfile.ZipFile(archive,'w') as z:z.writestr(bad,'bad')
        with patch.object(u,'fetch',fetch):
            try:u.stage_update(target,dict(sha=sha,version='0.29'),cancel)
            except ValueError:pass
            else:raise AssertionError('Unsafe archive accepted')
        assert not list((target/'Updates').glob('download-*')) and private.read_text()=='keep private'
    # Cancellation leaves no staging clutter.
    cancel.set()
    with patch.object(u,'fetch',fetch):
        try:u.stage_update(target,dict(sha=sha,version='0.29'),cancel)
        except u.UpdateCancelled:pass
        else:raise AssertionError('Cancellation ignored')
    assert not list((target/'Updates').glob('download-*'))
    # Run the detached helper in a real subprocess, with a stub verified runtime.
    fixture(target,'0.28','old');job=target/'Updates/download-handoff';package=job/'payload';package.mkdir(parents=True);fixture(package,'0.29','new from child')
    runtime=target/'Runtime/venv/bin/python';runtime.parent.mkdir(parents=True);runtime.write_text('#!/bin/sh\nexit 0\n');runtime.chmod(0o755)
    result=subprocess.run([sys.executable,str(Path(a.__file__)),'--target',str(target),'--package',str(package),'--pid','2000000000'],capture_output=True,text=True)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert (target/'Development/app.py').read_text()=='new from child' and private.read_text()=='keep private' and not job.exists()
print('Updates: pinned GitHub check, HTTPS boundaries, archive validation/checksums, stable icon, private settings preservation, interrupted-copy rollback and cancellation cleanup passed.')
