"""Non-destructive take storage, audio export, and source-conditioned editing.

ACE-Step supplies a candidate. Local assembly keeps original PCM outside the
chosen region instead of trusting the model to leave the rest alone.
"""
import json, math, shutil, tempfile, time, uuid
from pathlib import Path
from engine import binary, music_duration
from music_generator import (AceClient, LocalServer, MusicError, STYLE_KEYS,
    check_cancel, generation_request, run_ffmpeg)

AUDIO_SUFFIXES={'.wav','.flac','.mp3','.m4a','.aac','.aiff','.aif','.ogg','.opus','.wma'}
OPERATIONS=[('Generate a new song or instrumental','new'),
    ('Replace a selected passage / change lyrics','repaint'),
    ('Extend the ending to fit the slideshow','extend'),
    ('Trim to the slideshow length (no AI)','trim'),
    ('Add an instrument over the original recording','layer')]
INSTRUMENTS={'Piano / keyboards':'keyboard','Guitar':'guitar','Bass':'bass',
    'Drums':'drums','Percussion':'percussion','Strings':'strings',
    'Brass':'brass','Woodwinds':'woodwinds','Synthesizer':'synth'}
BASE_MODEL='acestep-v15-base'

def metadata_for(path):
    try:
        value=json.loads(Path(path).with_suffix('.json').read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}

def take_style(metadata):
    """Older takes have only prompt, mode and lyrics; recover useful controls."""
    style=metadata.get('style',{})
    style={k:v for k,v in style.items() if k in STYLE_KEYS and isinstance(v,str)} if isinstance(style,dict) else {}
    if not style and isinstance(metadata.get('prompt'),str):style['details']=metadata['prompt']
    for old,new in [('mode','music_mode'),('lyrics','lyrics'),('voice','voice'),('language','language'),('topic','topic')]:
        if new not in style and isinstance(metadata.get(old),str):style[new]=metadata[old]
    # Loading a finished song should edit its actual returned lyrics, not write
    # a different set from its old topic on the next source-conditioned edit.
    if style.get('lyrics','').strip() and style.get('music_mode')=='topic':style['music_mode']='lyrics'
    return style

def list_takes(directory):
    root=Path(directory)
    if not root.is_dir():return []
    return sorted((p for p in root.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES and '.partial.' not in p.name and not p.stem.endswith(' - instrument')),key=lambda p:p.stat().st_mtime,reverse=True)

def import_take(source,directory,cancel):
    source=Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in AUDIO_SUFFIXES:raise MusicError('Choose a readable audio file, such as WAV, FLAC, MP3, M4A or AIFF.')
    seconds=music_duration(source,cancel)
    if not math.isfinite(seconds) or seconds<=0:raise MusicError('This file does not contain a readable audio track.')
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    if source.parent==directory:return str(source)
    dest=directory/(source.stem[:80]+' '+uuid.uuid4().hex[:12]+source.suffix.lower())
    copy_audio(source,dest,cancel)
    metadata=metadata_for(source);metadata.update(imported_from=source.name,requested_seconds=seconds)
    dest.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
    return str(dest)

def copy_audio(source,dest,cancel):
    check_cancel(cancel);created=False
    try:
        with Path(source).open('rb') as src,Path(dest).open('xb') as out:
            created=True
            while True:
                check_cancel(cancel);block=src.read(1024*1024)
                if not block:break
                out.write(block)
    except BaseException:
        if created:Path(dest).unlink(missing_ok=True)
        raise

def export_take(source,dest,cancel):
    source=Path(source).resolve();dest=Path(dest).expanduser().resolve()
    if source==dest:raise MusicError('Choose a different filename; your working take is kept unchanged.')
    codecs={'.wav':['-c:a','pcm_s24le'],'.flac':['-c:a','flac'],'.mp3':['-c:a','libmp3lame','-b:a','320k']}
    if dest.suffix.lower() not in codecs:raise MusicError('Save as WAV, FLAC or MP3.')
    dest.parent.mkdir(parents=True,exist_ok=True)
    pending=dest.with_name('.'+dest.stem+'.'+uuid.uuid4().hex[:8]+'.partial'+dest.suffix)
    try:
        if source.suffix.lower()==dest.suffix.lower():copy_audio(source,pending,cancel)
        else:run_ffmpeg([binary('ffmpeg'),'-v','error','-y','-i',str(source),'-map','0:a:0','-vn']+codecs[dest.suffix.lower()]+[str(pending)],cancel)
        check_cancel(cancel);pending.replace(dest)
    finally:pending.unlink(missing_ok=True)
    metadata=metadata_for(source)
    if metadata:
        try:dest.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
        except OSError as error:raise MusicError('The audio was saved, but its companion lyrics/settings file could not be saved: '+str(error)) from error
    return str(dest)

def validate_edit(options,target,duration):
    operation=options.get('operation','new')
    if operation not in dict((value,label) for label,value in OPERATIONS) or operation=='new':raise MusicError('Choose an audio editing operation.')
    if not all(math.isfinite(n) and n>0 for n in (target,duration)):raise MusicError('The source and target durations must be positive.')
    if operation!='trim' and max(target if operation=='extend' else duration,duration)>600:raise MusicError('AI audio edits currently support source/result lengths up to ten minutes. Trim a shorter copy first; the original will be kept.')
    if operation=='extend' and target<=duration+.05:raise MusicError('This track is already as long as the slideshow. Use Trim for a shorter result, or increase the slideshow duration before extending.')
    if operation=='trim' and target>=duration:raise MusicError('Trim requires a slideshow shorter than the source. Use Extend for a longer result.')
    if operation=='repaint':
        start=float(options.get('edit_start',0));end=float(options.get('edit_end',duration))
        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end>duration+.001 or end-start<.1:raise MusicError('Select a passage with an end after its start, within the source duration (at least 0.1 seconds).')
    if operation=='layer' and options.get('instrument') not in INSTRUMENTS:raise MusicError('Choose an instrument to add.')
    if operation=='layer' and not 0<=float(options.get('layer_volume',35))<=100:raise MusicError('New instrument volume must be between 0 and 100 percent.')
    if operation in ('repaint','extend') and options.get('music_mode')=='topic':raise MusicError('For audio edits, choose Instrumental or Use my lyrics. Topic mode creates a new song; it cannot reliably preserve the existing words. You can paste the revised lyrics below.')

def normalize(source,dest,seconds,cancel):
    run_ffmpeg([binary('ffmpeg'),'-v','error','-y','-i',str(source),'-map','0:a:0','-af',f'aresample=48000,aformat=channel_layouts=stereo,apad,atrim=end_sample={round(seconds*48000)}','-c:a','pcm_s24le',str(dest)],cancel)

def splice(original,candidate,start,end,seconds,output,cancel):
    """Crossfades stay INSIDE the edited interval. Untouched samples are copied."""
    edge=min(.04,(end-start)/4);graph=[];pieces=[]
    def cut(index,a,b,label):
        graph.append(f'[{index}:a]atrim=start_sample={round(a*48000)}:end_sample={round(b*48000)},asetpts=PTS-STARTPTS[{label}]')
    if start>0:cut(0,0,start+edge,'before');pieces.append('before')
    cut(1,start,end,'edit');pieces.append('edit')
    if end<seconds:cut(0,end-edge,seconds,'after');pieces.append('after')
    label=pieces[0]
    for i,piece in enumerate(pieces[1:]):
        new=f'joined{i}';graph.append(f'[{label}][{piece}]acrossfade=ns={round(edge*48000)}:c1=tri:c2=tri[{new}]');label=new
    graph.append(f'[{label}]atrim=end_sample={round(seconds*48000)}[out]')
    run_ffmpeg([binary('ffmpeg'),'-v','error','-y','-i',str(original),'-i',str(candidate),'-filter_complex',';'.join(graph),'-map','[out]','-c:a','pcm_s24le',str(output)],cancel)

def edit_soundtrack(options,seconds,output,cancel,status):
    source=Path(options.get('source_audio','')).expanduser().resolve()
    if not source.is_file():raise MusicError('Load a source audio track before editing.')
    duration=music_duration(source,cancel);validate_edit(options,seconds,duration)
    operation=options['operation'];length=seconds if operation in ('extend','trim') else duration
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    client=AceClient(options.get('url','http://127.0.0.1:8001'),options.get('token',''));server=LocalServer();info=[]
    pending=output.with_name(output.stem+'.partial.wav');stem_saved=None
    try:
        with tempfile.TemporaryDirectory(prefix='stereo-audio-edit-') as tmp:
            temp=Path(tmp);original=temp/'source.wav';status('Preparing a working copy of the original audio…');normalize(source,original,length,cancel)
            if operation=='trim':shutil.copyfile(original,pending)
            else:
                base=operation=='layer'
                if base:status('Loading the Base model for instrument generation. First use may download model files…')
                server.ensure(client,options.get('folder',''),Path(options['logs']),cancel,status,need_lm=False,model=BASE_MODEL if base else None)
                payload=generation_request(dict(options,music_mode='instrumental') if base else options,length);payload.update(src_audio_path=str(original.resolve()),task_type='lego' if base else 'repaint',thinking=False,sample_mode=False,use_cot_metas=False,chunk_mask_mode='explicit')
                if base:
                    models=client.request('/v1/models');models=models.get('models',[]) if isinstance(models,dict) else []
                    names=[m.get('name','') for m in models if isinstance(m,dict)]
                    if BASE_MODEL not in names:raise MusicError('Adding instruments needs ACE-Step’s acestep-v15-base model. Close any separately running ACE-Step API and retry so this app can start Base, or load Base in that API first. Your original track has not changed.')
                    track=INSTRUMENTS[options['instrument']];payload.update(model=BASE_MODEL,inference_steps=50,track_name=track,instruction=f'Generate the {track.upper()} track based on the audio context:',repainting_start=0,repainting_end=duration)
                    payload['lyrics']='[Instrumental]'
                    payload['prompt']=f"{options['instrument']} accompaniment only, following the tempo, key and arrangement of the source recording. "+options.get('details','')
                else:
                    start=max(0,duration-.5) if operation=='extend' else float(options['edit_start']);end=length if operation=='extend' else float(options['edit_end'])
                    payload.update(repainting_start=start,repainting_end=end,instruction='Repaint the mask area based on the given conditions:')
                status('Requesting an instrument part…' if base else 'Requesting a replacement passage…')
                url=client.generate(payload['prompt'],length,cancel,status,payload=payload,result_info=info)
                raw=temp/'candidate.wav';client.download(url,raw,cancel)
                # Do not pad an incomplete AI response into a silent replacement.
                if music_duration(raw,cancel)+.10<length:raise MusicError('ACE-Step returned audio shorter than the requested edit. Your source is safe; try again or check its model/task support.')
                candidate=temp/'normalized.wav';normalize(raw,candidate,length,cancel)
                if base:
                    status('Mixing the new instrument over your original recording…')
                    gain=float(options.get('layer_volume',35))/100
                    graph=f'[0:a][1:a]amix=inputs=2:weights=1 {gain:g}:normalize=0,alimiter=limit=0.98:level=0:latency=1,atrim=end_sample={round(length*48000)}[out]'
                    run_ffmpeg([binary('ffmpeg'),'-v','error','-y','-i',str(original),'-i',str(candidate),'-filter_complex',graph,'-map','[out]','-c:a','pcm_s24le',str(pending)],cancel)
                    stem_saved=output.with_name(output.stem+' - instrument.wav');check_cancel(cancel);shutil.copyfile(candidate,stem_saved)
                else:
                    status('Keeping the original audio outside the edited passage…');splice(original,candidate,start,end,length,pending,cancel)
            check_cancel(cancel);pending.replace(output)
        source_meta=metadata_for(source)
        saved_style={k:options.get(k,'') for k in STYLE_KEYS}
        if operation in ('layer','trim'):
            saved_style.update(take_style(source_meta))
        elif operation=='extend' and options.get('music_mode')=='lyrics':
            old=source_meta.get('lyrics','').strip();new=options.get('lyrics','').strip()
            saved_style['lyrics']=old+'\n\n'+new if old and new and old not in new else new or old
        metadata=dict(style=saved_style,operation=operation,source_name=source.name,requested_seconds=length,slideshow_seconds=seconds,mode=saved_style.get('music_mode','instrumental'),lyrics=saved_style.get('lyrics',''),engine='Local trim' if operation=='trim' else 'ACE-Step 1.5',created=time.strftime('%Y-%m-%d %H:%M:%S'))
        for key in ('edit_start','edit_end','instrument','layer_volume'):
            if key in options:metadata[key]=options[key]
        if stem_saved:metadata['instrument_file']=stem_saved.name
        output.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
        return str(output)
    finally:
        pending.unlink(missing_ok=True)
        if stem_saved and not output.exists():stem_saved.unlink(missing_ok=True)
        server.stop()
