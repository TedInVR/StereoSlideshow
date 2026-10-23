"""Portable projects: copy media first, atomically commit a relative-path JSON file."""
import json,os,threading,time,uuid
from pathlib import Path
from output_names import safe_title
FORMAT='StereoSlideshowProject'
EXT='.stereoslideshow'
class ProjectError(ValueError):pass
class ProjectCancelled(Exception):pass

def new_project_path(parent,title):
    parent=Path(parent);stem=safe_title(title) or 'Untitled';name=stem+' StereoSlideshow Project';folder=parent/name;index=2
    while folder.exists():folder=parent/(name+f' {index}');index+=1
    return folder/(stem+EXT)

def _asset(root,relative):
    if not isinstance(relative,str) or Path(relative).is_absolute():raise ProjectError('The project contains an invalid media path.')
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):raise ProjectError('The project contains a media path outside its folder.')
    return path

def read_project(file):
    file=Path(file).resolve()
    try:data=json.loads(file.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:raise ProjectError('Could not read this project file: '+str(error)) from error
    if not isinstance(data,dict) or data.get('format')!=FORMAT or data.get('version')!=1:raise ProjectError('This is not a supported Stereo Slideshow project.')
    if not isinstance(data.get('settings'),dict) or not isinstance(data.get('media'),list) or not isinstance(data.get('music'),list):raise ProjectError('The project file is incomplete.')
    if not isinstance(data.get('captions',{}),dict):raise ProjectError('The caption data is not valid.')
    missing=[]
    for item in data['media']+data['music']:
        if not isinstance(item,dict) or not isinstance(item.get('path'),str):raise ProjectError('The project contains an invalid media entry.')
        path=_asset(file.parent,item['path']);item['resolved']=str(path)
        if not path.is_file():missing.append(path.name)
    if missing:raise ProjectError('Project media is missing: '+', '.join(missing[:8])+'. Restore the project’s Media folder before opening it.')
    data['captions']={str(_asset(file.parent,key)):str(value) for key,value in data.get('captions',{}).items()}
    return data

def save_project(file,snapshot,cancel=None,progress=lambda *args:None):
    file=Path(file).resolve();cancel=cancel or threading.Event();root=file.parent
    old={}
    if file.exists():
        # Never replace an unrelated JSON file or unsupported project.
        read_project(file)
        original=json.loads(file.read_text(encoding='utf-8'));old={entry.get('source'):entry for entry in original['media']+original['music']}
    root.mkdir(parents=True,exist_ok=True);assets=root/'Media';assets.mkdir(exist_ok=True)
    sources=list(dict.fromkeys([item['path'] for item in snapshot['media']]+snapshot['music']));mapping={}
    for index,source in enumerate(sources):
        if cancel.is_set():raise ProjectCancelled()
        path=Path(source).expanduser().resolve()
        try:before=path.stat()
        except OSError as error:raise ProjectError('Cannot save missing media: '+path.name) from error
        if not path.is_file():raise ProjectError('Not a media file: '+path.name)
        progress(index,len(sources),'Copying '+path.name)
        if path.is_relative_to(root) and path.parent==assets:
            target=path
        else:
            previous=old.get(source)
            target=_asset(root,previous['path']) if previous and previous.get('stamp')==[before.st_size,before.st_mtime_ns] else None
            if target is None or not target.is_file():
                target=assets/path.name;number=2
                while target.exists():target=assets/(path.stem+f'_{number}'+path.suffix);number+=1
                temporary=assets/('.'+uuid.uuid4().hex+'.partial')
                try:
                    with path.open('rb') as src,temporary.open('xb') as dest:
                        copied_bytes=0;last_update=time.monotonic()
                        while True:
                            if cancel.is_set():raise ProjectCancelled()
                            block=src.read(1024*1024)
                            if not block:break
                            dest.write(block);copied_bytes+=len(block)
                            if time.monotonic()-last_update>.25:
                                progress(index,len(sources),f'Copying {path.name} — {copied_bytes/1048576:.1f} of {before.st_size/1048576:.1f} MB');last_update=time.monotonic()
                        dest.flush();os.fsync(dest.fileno())
                    after=path.stat()
                    if (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns):raise ProjectError('A source changed while saving: '+path.name+'. Save the project again.')
                    temporary.replace(target)
                finally:temporary.unlink(missing_ok=True)
        mapping[source]={'path':str(target.relative_to(root)),'source':source,'stamp':[before.st_size,before.st_mtime_ns]}
    media=[dict(mapping[item['path']],sound=item.get('sound',True)) for item in snapshot['media']]
    music=[dict(mapping[source]) for source in snapshot['music']]
    captions={mapping[source]['path']:caption for source,caption in snapshot.get('captions',{}).items() if source in mapping}
    data=dict(format=FORMAT,version=1,settings=snapshot['settings'],media=media,music=music,captions=captions)
    if cancel.is_set():raise ProjectCancelled()
    temporary=root/('.'+uuid.uuid4().hex+'.project.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as handle:json.dump(data,handle,ensure_ascii=False,indent=2);handle.flush();os.fsync(handle.fileno())
        temporary.replace(file)
    finally:temporary.unlink(missing_ok=True)
    progress(len(sources),len(sources),'Project saved')
    return str(file)
