"""Portable timeline timing, media integrity, muted clips and cancellation."""
import json,sys,tempfile,threading,wave,zipfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from PIL import Image
from engine import Cancelled,binary
from resolve_export import export_timeline

def load(folder):
    with zipfile.ZipFile(Path(folder)/'Edit in Resolve.otioz') as z:
        assert z.testzip() is None and z.read('version.txt')==b'1.0.0'
        data=json.loads(z.read('content.otio'));names=z.namelist()
        for track in data['tracks']['children']:
            for clip in track['children']:
                if 'media_reference' in clip:
                    url=clip['media_reference']['target_url'];assert url in names and not url.startswith('/')
                    assert clip['source_range']['duration']['value']<=clip['media_reference']['available_range']['duration']['value']
        return data
def frames(track):return sum(c['source_range']['duration']['value'] for c in track['children'])
with tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/'a').mkdir();(root/'b').mkdir()
    p=root/'a/Photo.jpg';p2=root/'b/Photo.jpg'
    Image.new('RGB',(120,80),'red').save(p);Image.new('RGB',(120,80),'blue').save(p2)
    wav=root/'Song.wav'
    with wave.open(str(wav),'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*16000)
    video=root/'Video.mp4'
    subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=red:s=120x80:r=30:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(video)],check=True)
    snap=dict(media=[dict(path=str(p),sound=True),dict(path=str(p2),sound=True),dict(path=str(video),sound=True)],music=[str(wav)],captions={str(p):'Mom, at the beach'})
    cfg=dict(fps=30,seconds=5,pause=1,title='Editable test',title_seconds=2,closing_fade=6,video_sound=True,width=3840,height=1080)
    folder=export_timeline(root,snap,cfg,threading.Event());data=load(folder);tracks=data['tracks']['children']
    assert [frames(t) for t in tracks]==[660,660,660]
    assert len(tracks[1]['children'])==11 # loop 2-second song across 22 seconds
    assert len(tracks[2]['children'])==3 and tracks[2]['children'][1]['name']=='Video.mp4 — sound'
    assert tracks[0]['children'][-2]['name'].startswith('Closing frame')
    refs=[c['media_reference']['target_url'] for c in tracks[0]['children'] if 'media_reference' in c]
    assert refs[0]!=refs[1] # identical basenames do not collide
    assert 'Mom, at the beach' in (Path(folder)/'Caption cues.csv').read_text(encoding='utf-8-sig')
    assert str(root) not in json.dumps(data)
    # Official SDK independently deserializes and extracts the actual ZIP format.
    try:import opentimelineio as otio
    except ImportError:otio=None
    if otio:
        extracted=root/'extracted';extracted.mkdir()
        timeline=otio.adapters.read_from_file(str(Path(folder)/'Edit in Resolve.otioz'),adapter_name='otioz',extract_to_directory=str(extracted))
        assert timeline.duration().to_seconds()==22 and len(list(timeline.find_clips()))==16
        assert all(t.duration().to_seconds()==22 for t in timeline.tracks)
        assert len(list(extracted.rglob('*.jpg')))==2
    # Mute either per clip or globally, without changing the picture timing.
    cfg['video_sound']=False
    muted=load(export_timeline(root,snap,cfg,threading.Event()))
    assert len(muted['tracks']['children'][2]['children'])==1
    cfg['video_sound']=True;snap['media'][-1]['sound']=False
    muted=load(export_timeline(root,snap,cfg,threading.Event()))
    assert len(muted['tracks']['children'][2]['children'])==1
    # Music-end trimming and exact auto-fit share the app's frame planner.
    cfg.update(title='',pause=0,closing_fade=.5,end_mode='music')
    trim=load(export_timeline(root,snap,cfg,threading.Event()))
    assert all(frames(t)==60 for t in trim['tracks']['children'])
    assert not any(c['name']=='Video.mp4' for c in trim['tracks']['children'][0]['children'])
    cfg['fit_music']=True;snap['media']=snap['media'][:2]
    fit=load(export_timeline(root,snap,cfg,threading.Event()))
    assert all(frames(t)==60 for t in fit['tracks']['children'])
    # A mid-copy cancellation leaves prior exports and original media intact.
    before=set(root.iterdir());cancel=threading.Event()
    def stop(i,total,text):
        if text.startswith('Bundling'):cancel.set()
    try:export_timeline(root,snap,cfg,cancel,stop)
    except Cancelled:pass
    else:raise AssertionError('Cancellation ignored')
    assert set(root.iterdir())==before and p.is_file() and video.is_file()
print('Resolve export: portable OTIOZ/SDK read-back, original media, duplicate names, separate looped music, clip muting, final holds, trim/auto-fit timing and cancellation passed.')
