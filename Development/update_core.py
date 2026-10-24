"""Public GitHub updates, pinned to a commit and verified before installation."""
import json,re,shutil,stat,subprocess,sys,tempfile,urllib.request,zipfile
from pathlib import Path,PurePosixPath
from install_support import ID,verify_package
REPO='TedInVR/StereoSlideshow'
HOSTS={'api.github.com','github.com','codeload.github.com','raw.githubusercontent.com'}
LIMIT=100*1024*1024
class UpdateCancelled(Exception):pass

def checkpoint(cancel):
    if cancel.is_set():raise UpdateCancelled()

def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d+(?:\.\d+){1,3}',value):raise ValueError('Unrecognized update version.')
    parts=[int(x) for x in value.split('.')];return tuple(parts+[0]*(4-len(parts)))

def safe_url(url):
    from urllib.parse import urlparse
    p=urlparse(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.username or p.password:raise ValueError('Unexpected update download address.')
    return url

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return super().redirect_request(req,fp,code,msg,headers,safe_url(newurl))

def fetch(url,destination,cancel,progress=lambda *args:None,limit=LIMIT):
    request=urllib.request.Request(safe_url(url),headers={'User-Agent':'StereoSlideshow-Updater','Accept':'application/vnd.github+json'})
    opener=urllib.request.build_opener(Redirect())
    with opener.open(request,timeout=20) as response,open(destination,'wb') as out:
        safe_url(response.geturl());size=int(response.headers.get('Content-Length') or 0)
        if size>limit:raise ValueError('The update download is larger than expected.')
        count=0
        while True:
            checkpoint(cancel);block=response.read(128*1024)
            if not block:break
            count+=len(block)
            if count>limit:raise ValueError('The update download is larger than expected.')
            out.write(block);progress(count,size,'Downloading update…')

def read_json(url,cancel):
    with tempfile.TemporaryDirectory() as td:
        dest=Path(td)/'response.json';fetch(url,dest,cancel,limit=1024*1024)
        return json.loads(dest.read_text())

def check_update(current,cancel):
    data=read_json(f'https://api.github.com/repos/{REPO}/commits/main',cancel);sha=data.get('sha','')
    if not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('GitHub returned an invalid update identifier.')
    project=read_json(f'https://raw.githubusercontent.com/{REPO}/{sha}/project.json',cancel)
    if project.get('identifier')!=ID:raise ValueError('This update belongs to a different application.')
    return dict(sha=sha,version=project['version'],available=version(project['version'])>version(current))

def allowed(relative):
    path=PurePosixPath(relative)
    if not relative or '\\' in relative or path.is_absolute() or '..' in path.parts or '.' in path.parts:raise ValueError('Unsafe update path.')
    if path.parts[0] not in {'Development','Stereo Slideshow.app','tests','tools','.gitignore','README.md','START HERE.txt','project.json','manifest.json','Install or Update.command'}:raise ValueError('Update attempted to replace user data.')
    return path

def validate(package,expected=None):
    manifest=verify_package(package)
    if not isinstance(manifest.get('sha256'),dict) or not manifest['sha256']:raise ValueError('Empty update manifest.')
    for name,digest in manifest['sha256'].items():
        allowed(name)
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid update checksum.')
    project=json.loads((package/'project.json').read_text())
    if manifest.get('version')!=project.get('version') or (expected and project.get('version')!=expected):raise ValueError('The downloaded update version does not match.')
    for needed in ['Development/app.py','Development/requirements.txt','project.json','Stereo Slideshow.app/Contents/MacOS/launch']:
        if needed not in manifest['sha256']:raise ValueError('The update is missing required program files.')
    return manifest

def stage_update(root,release,cancel,progress=lambda *args:None):
    updates=Path(root)/'Updates';updates.mkdir(parents=True,exist_ok=True)
    job=Path(tempfile.mkdtemp(prefix='download-',dir=updates))
    try:
        archive=job/'update.zip'
        fetch(f"https://api.github.com/repos/{REPO}/zipball/{release['sha']}",archive,cancel,progress)
        package=job/'payload';package.mkdir()
        with zipfile.ZipFile(archive) as z:
            entries=z.infolist()
            if len(entries)>10000 or sum(e.file_size for e in entries)>300*1024*1024:raise ValueError('The update archive is larger than expected.')
            roots=set();seen=set()
            for entry in entries:
                checkpoint(cancel);name=entry.filename;path=PurePosixPath(name)
                if '\\' in name or path.is_absolute() or '..' in path.parts or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Unsafe archive entry.')
                if not path.parts:continue
                roots.add(path.parts[0])
                if len(roots)!=1:raise ValueError('Unexpected archive layout.')
                if len(path.parts)==1 or entry.is_dir():continue
                relative='/'.join(path.parts[1:]);allowed(relative)
                if relative in seen:raise ValueError('Duplicate archive entry.')
                seen.add(relative);dest=package/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(entry) as source,dest.open('wb') as out:
                    while True:
                        checkpoint(cancel);block=source.read(1024*1024)
                        if not block:break
                        out.write(block)
                if entry.external_attr>>16&0o111:dest.chmod(0o755)
        progress(0,0,'Verifying update files…');checkpoint(cancel);validate(package,release['version']);archive.unlink()
        return dict(package=str(package),job=str(job),version=release['version'])
    except BaseException:
        shutil.rmtree(job,ignore_errors=True);raise

def launch_installer(root,download,pid):
    """Copy the current helper away from files that it will replace after exit."""
    root=Path(root);job=Path(download['job']);package=Path(download['package'])
    if job.parent.resolve()!=(root/'Updates').resolve() or package.parent.resolve()!=job.resolve():raise ValueError('Unexpected update staging folder.')
    validate(package,download['version'])
    for name in ['update_apply.py','update_core.py','install_support.py']:shutil.copy2(root/'Development'/name,job/name)
    log=root/'Logs/update.log';log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('a') as output:
        subprocess.Popen([sys.executable,str(job/'update_apply.py'),'--target',str(root),'--package',str(package),'--pid',str(pid)],stdout=output,stderr=output,start_new_session=True)
