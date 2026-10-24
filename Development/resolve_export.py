"""Portable source-edit timelines. No Resolve installation or OTIO SDK required."""
import csv
import json
import math
import tempfile
import uuid
import zipfile
from pathlib import Path
from engine import VIDEO_EXT, Cancelled, binary, check_photo, music_duration, run, video_info
from output_names import safe_title
from timing import make_plan

def rational(value, fps):
    return dict(OTIO_SCHEMA='RationalTime.1', value=float(value), rate=float(fps))

def span(frames, fps, start=0):
    return dict(OTIO_SCHEMA='TimeRange.1', start_time=rational(start,fps), duration=rational(frames,fps))

def composition(schema, name, children):
    return dict(OTIO_SCHEMA=schema, name=name, metadata={}, source_range=None,
                effects=[], markers=[], enabled=True, children=children)

def gap(frames, fps, name='Black / silence'):
    return dict(OTIO_SCHEMA='Gap.1', name=name, metadata={}, source_range=span(frames,fps), effects=[], markers=[], enabled=True)

def clip(name, url, frames, fps, available, metadata=None):
    # Clip.1 is the widely supported single-reference schema, upgraded by OTIO readers.
    return dict(OTIO_SCHEMA='Clip.1', name=name, metadata=metadata or {}, source_range=span(frames,fps),
                effects=[], markers=[], enabled=True, media_reference=dict(OTIO_SCHEMA='ExternalReference.1',
                name='', metadata={}, target_url=url, available_range=span(available,fps)))

def export_timeline(parent, snapshot, cfg, cancel, progress=lambda *args:None):
    """Commit a new export folder only after its complete archive has been written."""
    records=snapshot['media']; music=snapshot['music']
    if not records:raise ValueError('Add at least one photo or video first.')
    parent=Path(parent);parent.mkdir(parents=True,exist_ok=True)
    title=cfg.get('title','').strip() or 'Untitled slideshow';stem=(safe_title(title) or 'Slideshow')+' Resolve Export'
    target=parent/stem
    while target.exists():target=parent/(stem+' '+uuid.uuid4().hex[:6])
    fps=cfg.get('fps',30);durations=[];infos={};audio_lengths=[]
    def checkpoint():
        if cancel.is_set():raise Cancelled()
    for i,record in enumerate(records):
        checkpoint();path=record['path'];progress(0,1,'Reading '+Path(path).name)
        if Path(path).suffix.lower() in VIDEO_EXT:
            infos[path]=video_info(path,cancel);durations.append(infos[path]['duration'])
        else:check_photo(path);durations.append(None)
    for path in music:checkpoint();audio_lengths.append(music_duration(path,cancel))
    plan=make_plan(durations,sum(audio_lengths) if music else None,cfg)
    total=plan['total'];visuals=[];audio=[];song=[];cues=[];assets={}
    def asset(path):
        path=str(Path(path).resolve())
        if path not in assets:
            clean=safe_title(Path(path).stem) or 'Media'
            assets[path]=f'media/{len(assets)+1:04}_{clean[:90]}{Path(path).suffix.lower()}'
        return assets[path]
    if plan['intro']:visuals.append(gap(plan['intro'],fps,'Opening — add title: '+title))
    audio_cursor=0;last=None
    for record,duration,item in zip(records,durations,plan['items']):
        count=max(0,min(item['frames'],plan['fade_start']-item['start']))
        if not count:continue
        path=record['path'];url=asset(path);available=max(count,math.ceil(duration*fps)) if duration else total
        caption=snapshot.get('captions',{}).get(path,'')
        visuals.append(clip(Path(path).name,url,count,fps,available,{'StereoSlideshow':{'caption':caption}}))
        cues.append([item['start']/fps,(item['start']+count)/fps,Path(path).name,caption])
        last=(path,duration,count)
        if duration and cfg.get('video_sound',True) and record.get('sound',True) and infos[path]['has_audio']:
            if item['start']>audio_cursor:audio.append(gap(item['start']-audio_cursor,fps))
            audio.append(clip(Path(path).name+' — sound',url,count,fps,available));audio_cursor=item['start']+count
    if not last:raise ValueError('The selected timing leaves no room for any photos or videos.')
    end=min(plan['content_cursor'],plan['fade_start']);hold=total-plan['tail']-end
    with tempfile.TemporaryDirectory(prefix='.resolve-working-',dir=parent) as temporary:
        work=Path(temporary);package=work/'bundle';package.mkdir()
        if hold:
            path,duration,count=last
            if duration is None:
                visuals[-1]['source_range']['duration']=rational(count+hold,fps)
            else:
                freeze=work/'Closing frame.png'
                run([binary('ffmpeg'),'-y','-ss',str(max(0,(count-1)/fps)),'-i',path,'-map',f"0:{infos[path]['stream']}",'-frames:v','1',str(freeze)],cancel)
                visuals.append(clip('Closing frame — add fade to black',asset(freeze),hold,fps,hold))
        if plan['tail']:visuals.append(gap(plan['tail'],fps))
        if audio_cursor<total:audio.append(gap(total-audio_cursor,fps))
        cursor=0;index=0
        # Cumulative rounding keeps consecutive songs aligned without accumulating frame error.
        seconds=0
        while music and cursor<total:
            checkpoint();j=index%len(music);seconds+=audio_lengths[j]
            boundary=max(cursor+1,round(seconds*fps));count=min(total-cursor,boundary-cursor)
            song.append(clip(Path(music[j]).name,asset(music[j]),count,fps,max(count,math.ceil(audio_lengths[j]*fps))))
            cursor+=count;index+=1
        if not song:song.append(gap(total,fps))
        tracks=[]
        for name,kind,children in [('Photos and video — source edit','Video',visuals),('Music playlist','Audio',song),('Enabled video clip sound','Audio',audio)]:
            track=composition('Track.1',name,children);track['kind']=kind;tracks.append(track)
        metadata={'StereoSlideshow':{'stage':'Source edit; effects are not reproduced','fps':fps,'width':cfg.get('width',3840),'height':cfg.get('height',1080),'closing_fade_seconds':cfg.get('closing_fade',6),'source_cross_eye':cfg.get('cross',False),'video_half_sbs':cfg.get('video_half',False),'video_cross_eye':cfg.get('video_cross',False)}}
        timeline=dict(OTIO_SCHEMA='Timeline.1',name=title,metadata=metadata,global_start_time=rational(0,fps),tracks=composition('Stack.1','tracks',tracks))
        # All filenames inside OTIOZ are unique, flat and relative; no account settings are exported.
        archive=package/'Edit in Resolve.otioz'
        with zipfile.ZipFile(archive,'w',allowZip64=True) as z:
            z.writestr('version.txt','1.0.0',compress_type=zipfile.ZIP_DEFLATED)
            z.writestr('content.otio',json.dumps(timeline,ensure_ascii=False,indent=2),compress_type=zipfile.ZIP_DEFLATED)
            for i,(source,url) in enumerate(assets.items()):
                checkpoint();progress(i,len(assets),'Bundling '+Path(source).name)
                with open(source,'rb') as src,z.open(url,'w',force_zip64=True) as dest:
                    while True:
                        checkpoint();chunk=src.read(1024*1024)
                        if not chunk:break
                        dest.write(chunk)
        with (package/'Caption cues.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.writer(f);writer.writerow(['Start seconds','End seconds','Filename','Caption']);writer.writerows(cues)
        notes=f'''STEREO SLIDESHOW — EDITABLE SOURCE TIMELINE

1. In DaVinci Resolve 18.5 or newer, choose File > Import > Timeline.
2. Select "Edit in Resolve.otioz". Allow Resolve to extract the bundled media
   into a permanent folder. Keep that extracted folder with your Resolve project.
3. Check the timeline settings: {fps} fps, {cfg.get('width',3840)} × {cfg.get('height',1080)} pixels (full SBS).
   If necessary, disable automatic project settings and enter these dimensions.
4. Save the imported timeline as a normal Resolve project. You can now replace,
   move or trim individual source clips, and edit the music on its own track.

THIS IS A FIRST-STAGE SOURCE EDIT, NOT A FINISHED LOOK MATCH.
The source SBS photos/videos are copied unchanged. Resolve's default image
scaling may place eye views incorrectly for media with different aspect ratios.
Set up left/right eye framing in Resolve before judging or exporting stereo.
Cross-eye and half-SBS inputs also need their eye order/aspect corrected there.
The app's stereo backgrounds, animation, layer depth, titles, captions,
transitions, music ducking and fades are NOT recreated. The opening is an
empty title placeholder. Closing hold frames are included, but add the final
picture/audio fades in Resolve. Caption cues.csv supplies text and timings;
it is not a rendered stereo subtitle track. Music repeats/trims to timeline
length, without baked fades. Video sound is on a separate track and respects
the global clip-sound option and each clip's checkbox.

Title: {title}
Duration: {total/fps:.3f} seconds
Closing fade to add: {cfg.get('closing_fade',6)} seconds before the black tail.
Opening pause: {cfg.get('pause',1)} seconds
Title duration: {cfg.get('title_seconds',6) if cfg.get('title','').strip() else 0} seconds
Music-end timing may trim or omit later media, matching the app's timing plan.
Keep a saved Stereo Slideshow project and a finished MP4 as your visual reference.
After editing in Resolve, export full SBS and reapply the stereo metadata before
uploading. Importing a timeline does not preserve MP4 upload metadata.
'''
        (package/'READ ME.txt').write_text(notes,encoding='utf-8')
        checkpoint();package.rename(target)
    progress(1,1,'Resolve export ready')
    return str(target)
