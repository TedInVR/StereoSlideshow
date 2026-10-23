import os, math, subprocess, tempfile, shutil, json
from pathlib import Path
from timing import make_plan, TimingError
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageEnhance

class Cancelled(Exception): pass

class RenderError(Exception):
    def __init__(self,message,details=''):
        super().__init__(message);self.details=details

def log_tail(handle,limit=16000):
    handle.seek(0,os.SEEK_END);size=handle.tell();handle.seek(max(0,size-limit))
    return handle.read().decode(errors='replace')

def split_photo(src):
    """Equal eye crops; ignore the single seam column when packed width is odd."""
    sw,sh=src.size;eye_width=sw//2
    if eye_width<1 or sh<1:raise RenderError('A photo is too small to contain two eye views.')
    return [src.crop((0,0,eye_width,sh)),src.crop((sw-eye_width,0,sw,sh))]

def check_photo(path):
    try:
        with Image.open(path) as src:
            src.load();oriented=ImageOps.exif_transpose(src)
            if oriented.width<2 or oriented.height<1:raise ValueError('Image is too small for two eye views.')
            return oriented.size
    except Exception as e:
        raise RenderError('Could not read photo “'+Path(path).name[:140]+'”. Check that it opens normally, then try again.',repr(e)) from e


def binary(name):
    for p in [shutil.which(name), '/opt/homebrew/bin/'+name, '/usr/local/bin/'+name]:
        if p and os.path.isfile(p): return p
    raise RuntimeError('FFmpeg is missing. Install Homebrew FFmpeg, then try again.')

def run(args, cancel, message='A video or audio processing step failed. See the saved details for the affected file.'):
    if Path(args[0]).name=='ffmpeg':args=[args[0],'-hide_banner','-loglevel','error','-nostats']+args[1:]
    with tempfile.TemporaryFile() as log:
        p=subprocess.Popen(args, stdout=log, stderr=log)
        while p.poll() is None:
            if cancel.wait(.15):
                p.kill(); p.wait(); raise Cancelled()
        if p.returncode:
            raise RenderError(message,log_tail(log))

VIDEO_EXT={'.mp4','.mkv','.mov','.m4v','.avi','.webm','.mts','.m2ts'}

def media_info(path,cancel):
    with tempfile.TemporaryDirectory() as td:
        dest=Path(td)/'probe.json'
        run([binary('ffprobe'),'-v','error','-show_streams','-show_format','-of','json','-o',str(dest),path],cancel,
            'Could not read media file “'+Path(path).name[:140]+'”. Check that it plays normally, then try again.')
        return json.loads(dest.read_text())

def video_info(path,cancel):
    data=media_info(path,cancel)
    streams=data.get('streams',[])
    video=next((v for v in streams if v['codec_type']=='video' and not v.get('disposition',{}).get('attached_pic')),None)
    if video is None: raise RenderError('No video track was found in “'+Path(path).name[:140]+'”.')
    duration=float(video.get('duration') or data.get('format',{}).get('duration') or 0)
    if not math.isfinite(duration) or duration<=0: raise RenderError('Could not determine the length of “'+Path(path).name[:140]+'”.')
    if int(video['width'])%2: raise RenderError('Video “'+Path(path).name[:140]+'” has an odd pixel width. This video needs an even-width SBS frame.')
    return dict(duration=duration,stream=video['index'],has_audio=any(v['codec_type']=='audio' for v in streams))

def music_duration(path,cancel):
    data=media_info(path,cancel)
    track=next((v for v in data.get('streams',[]) if v.get('codec_type')=='audio'),None)
    if track is None:raise RenderError('No audio track was found in “'+Path(path).name[:140]+'”.')
    duration=float(track.get('duration') or data.get('format',{}).get('duration') or 0)
    if not math.isfinite(duration) or duration<=0:raise RenderError('Could not determine music length for “'+Path(path).name[:140]+'”.')
    return duration

def prepare_playlist(paths,destination,cancel):
    args=[binary('ffmpeg'),'-y']
    for path in paths:args+=['-i',path]
    filters=[];labels=[]
    for i in range(len(paths)):
        filters.append(f'[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[m{i}]');labels.append(f'[m{i}]')
    filters.append(''.join(labels)+f'concat=n={len(paths)}:v=0:a=1[playlist]')
    run(args+['-filter_complex',';'.join(filters),'-map','[playlist]','-c:a','pcm_f32le',str(destination)],cancel,
        'The music playlist could not be prepared. See the saved diagnostic report.')

class VideoReader:
    def __init__(self,path,info,w,h,fps,cfg):
        half='scale=iw*2:ih,' if cfg.get('video_half',False) else ''
        eye=f'{half}setsar=1,scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1'
        order='[r][l]' if cfg.get('video_cross',False) else '[l][r]'
        filt=f"[0:{info['stream']}]setpts=PTS-STARTPTS,fps={fps},split=2[a][b];[a]crop=iw/2:ih:0:0,{eye}[l];[b]crop=iw/2:ih:iw/2:0,{eye}[r];{order}hstack=inputs=2,format=rgb24[v]"
        self.log=tempfile.TemporaryFile();self.size=w*2*h*3;self.dims=(w*2,h);self.last=None
        self.proc=subprocess.Popen([binary('ffmpeg'),'-v','error','-threads','2','-i',path,'-filter_complex_threads','1','-filter_complex',filt,'-map','[v]','-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=self.log)
    def frame(self,allow_last=False):
        data=self.proc.stdout.read(self.size)
        if len(data)!=self.size:
            if allow_last and self.last is not None: return self.last
            raise RenderError('A video clip stopped decoding before its expected end.',log_tail(self.log))
        self.last=Image.frombytes('RGB',self.dims,data);return self.last
    def close(self):
        if self.proc.poll() is None:self.proc.kill()
        self.proc.wait();self.proc.stdout.close();self.log.close()

def font(size):
    for f in ['/System/Library/Fonts/Supplemental/Arial.ttf','/System/Library/Fonts/Helvetica.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if os.path.isfile(f): return ImageFont.truetype(f,size)
    return ImageFont.load_default(size=size)

def title_image(text,w,h,color):
    size=int(h*.105)
    while True:
        ft=font(size); lines=[]
        for paragraph in text.split('\n'):
            line=''
            for word in paragraph.split():
                test=(line+' '+word).strip()
                if ft.getlength(test)>w*.8 and line: lines.append(line); line=word
                else: line=test
            lines.append(line)
        im=Image.new('RGBA',(w,h)); d=ImageDraw.Draw(im)
        box=d.multiline_textbbox((0,0),'\n'.join(lines),font=ft,spacing=size//4,align='center')
        if (box[2]-box[0]<=w*.85 and box[3]-box[1]<h*.7) or size<=12: break
        size-=2
    d.multiline_text(((w-(box[2]-box[0]))/2-box[0],(h-(box[3]-box[1]))/2-box[1]),'\n'.join(lines),fill=color,font=ft,spacing=size//4,align='center')
    return im

def caption_image(text,w,h):
    text=text.strip()
    if not text:return None
    maxwidth=w*.82
    size=max(8,round(h*.038))
    while True:
        ft=font(size);lines=[]
        for paragraph in text.split('\n'):
            line=''
            for char in paragraph:
                if line and ft.getlength(line+char)>maxwidth:
                    split=line.rfind(' ')
                    if split>0:lines.append(line[:split]);line=line[split+1:]+char
                    else:lines.append(line);line=char
                else:line+=char
            lines.append(line.strip())
        layer=Image.new('RGBA',(w,h));d=ImageDraw.Draw(layer)
        box=d.multiline_textbbox((0,0),'\n'.join(lines),font=ft,spacing=max(2,size//4),align='center',stroke_width=1)
        tw,th=box[2]-box[0],box[3]-box[1]
        if th<h*.24 or size<=8:break
        size-=1
    x=(w-tw)/2-box[0];y=h*.93-th-box[1];pad=max(3,round(h*.012))
    d.rounded_rectangle((x+box[0]-pad,y+box[1]-pad,x+box[2]+pad,y+box[3]+pad),radius=pad,fill=(0,0,0,155))
    d.multiline_text((x,y),'\n'.join(lines),font=ft,fill='white',stroke_width=1,stroke_fill='black',spacing=max(2,size//4),align='center')
    return layer

def foreground_geometry(i,q,ew,eh,w,h,expressive,drift=.0015):
    fit=min(w*.94/ew,h*.94/eh,1)
    mode=i%8
    if expressive:
        if mode in (0,1,6,7):
            # At the near endpoint the frame shows the middle 80% of image height.
            near=h/(.8*eh)
            z=fit+(near-fit)*(1-q if mode==1 else q)
            x=(w-ew*z)/2; y=(h-eh*z)/2
        else:
            z=min(w*.8/ew,h*.96/eh)
            fw,fh=ew*z,eh*z
            if mode in (2,3):
                start=min(w*.10,max(0,(w-fw)*.4))
                end=min(w-fw,max(w*.50-fw,start+w*.06))
                left=start+(end-start)*q
                x=left if mode==2 else w-fw-left
                y=(h-fh)/2
            else:
                x=(w-fw)/2
                travel=min(h*.08,(h-fh)*.35)
                y=(h-fh)/2+(q-.5)*2*travel*(1 if mode==4 else -1)
        return z,x,y
    z=fit*(.98+.02*q if mode%2==0 else 1-.02*q)
    dx,dy=[(0,0),(0,0),(-1,0),(1,0),(0,-1),(0,1),(-1,1),(1,-1)][mode]
    tx=min(w*drift,max(0,(w-ew*z)/2)*.5)
    ty=min(h*drift,max(0,(h-eh*z)/2)*.5)
    return z,(w-ew*z)/2+dx*(q-.5)*2*tx,(h-eh*z)/2+dy*(q-.5)*2*ty

def render(images,audio,out,cfg,progress,cancel):
    ff=binary('ffmpeg'); w,h=cfg['width']//2,cfg['height']; fps=cfg['fps']
    playlist=[audio] if isinstance(audio,str) and audio else list(audio or [])
    playlist_seconds=0
    seconds=cfg['seconds']; fade=min(.65,seconds/3); intro=cfg['pause']+(cfg['title_seconds'] if cfg['title'].strip() else 0)
    items=[]; cursor=round(intro*fps); intro=cursor/fps
    for index,path in enumerate(images):
        if cancel.is_set(): raise Cancelled()
        is_video=Path(path).suffix.lower() in VIDEO_EXT
        progress(0,f'Checking {index+1} of {len(images)}: '+Path(path).name)
        info=video_info(path,cancel) if is_video else None
        if not is_video:check_photo(path)
        frames=max(1,math.ceil(info['duration']*fps) if is_video else round(seconds*fps))
        items.append(dict(path=path,video=is_video,info=info,start=cursor,frames=frames))
        cursor+=frames
    for track in playlist:
        progress(0,'Checking music: '+Path(track).name)
        playlist_seconds+=music_duration(track,cancel)
    if cancel.is_set():raise Cancelled()
    try:plan=make_plan([item['info']['duration'] if item['video'] else None for item in items],playlist_seconds if playlist else None,cfg)
    except TimingError as e:raise RenderError(str(e)) from e
    for item,position in zip(items,plan['items']):item.update(position)
    intro=plan['intro']/fps;seconds=plan['photo_seconds'];fade=min(.65,seconds/3)
    content_end=min(plan['content_cursor'],plan['fade_start']);fade_start=plan['fade_start']
    closing_frames=plan['closing'];closing_seconds=closing_frames/fps;count=plan['total'];total=count/fps
    bg=cfg['background']; photo_cache={}; backdrop_cache={}
    def photo(i):
        if i not in photo_cache:
            with Image.open(images[i]) as src:
                src=ImageOps.exif_transpose(src).convert('RGB')
                eyes=split_photo(src)
                if cfg['cross']: eyes.reverse()
                fitted=[]
                for eye in eyes:
                    eye.thumbnail((w*2,h*2),Image.Resampling.LANCZOS); fitted.append(eye)
                photo_cache[i]=fitted
                for k in list(photo_cache):
                    if abs(k-i)>1: del photo_cache[k]
        return photo_cache[i]
    def backdrop(i,q):
        style=cfg.get('background_style','Solid color')
        if style=='Solid color': return Image.new('RGB',(w*2,h),bg)
        previous=style=='Previous photo grows' and i>0 and not items[i-1]['video']
        source=i-1 if previous else i
        key=(source,previous)
        if key not in backdrop_cache:
            # Blur a matching eye pair; retain identical framing and processing.
            backdrop_cache.clear()
            backdrop_cache[key]=[e if style=='Sharp moving current photo' else ImageEnhance.Brightness(e.filter(ImageFilter.GaussianBlur(max(2,min(e.size)*.025)))).enhance(.30) for e in photo(source)]
        canvas=Image.new('RGB',(w*2,h),bg)
        for j,eye in enumerate(backdrop_cache[key]):
            cover=max(w/eye.width,h/eye.height)
            scale=(min(w*.94/eye.width,h*.94/eye.height)+(cover-min(w*.94/eye.width,h*.94/eye.height))*q) if previous else cover
            if style=='Sharp moving current photo': scale=cover*(1.04+.035*q if i%3==0 else 1.06)
            layered=cfg.get('depth_layers',True)
            separation=[.008,.012,.016][cfg.get('layer_strength',1)] if layered else 0
            # Extra image coverage avoids blank strips when shifting a filled backdrop.
            if not previous and layered:scale*=1+2*separation+.01
            x=(w-eye.width*scale)/2; y=(h-eye.height*scale)/2
            # Uncrossed disparity places the background plane behind the window.
            x+=(-1 if j==0 else 1)*w*separation
            if style=='Sharp moving current photo':
                if i%3==1: x+=(q-.5)*min(w*.04,max(0,eye.width*scale-w)*.8)
                if i%3==2: y+=(q-.5)*min(h*.04,max(0,eye.height*scale-h)*.8)
            view=eye.transform((w,h),Image.Transform.AFFINE,
                (1/scale,0,-x/scale,0,1/scale,-y/scale),Image.Resampling.BICUBIC,fillcolor=bg)
            canvas.paste(view,(j*w,0))
        return canvas
    def scene(i,t):
        eyes=photo(i); q=max(0,min(1,t/seconds)); q=q*q*(3-2*q)
        canvas=backdrop(i,q)
        for j,eye in enumerate(eyes):
            zoom,x,y=foreground_geometry(i,q,eye.width,eye.height,w,h,
                cfg.get('motion_style','Gentle')=='Closer zoom and side drift',cfg.get('drift',.0015))
            view=eye.convert('RGBA').transform((w,h),Image.Transform.AFFINE,
                (1/zoom,0,-x/zoom,0,1/zoom,-y/zoom),
                resample=Image.Resampling.BICUBIC,fillcolor=(0,0,0,0))
            canvas.paste(view,(j*w,0),view)
        return canvas
    title=title_image(cfg['title'],w,h,cfg['text_color']) if cfg['title'].strip() else None
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory(prefix='stereo-slideshow-') as td:
        soundtrack=playlist[0] if playlist else None
        if playlist and (len(playlist)>1 or cfg.get('end_mode')=='music' or cfg.get('fit_music',False)):
            progress(1,'Preparing ordered music playlist')
            soundtrack=str(Path(td)/'playlist.mka');prepare_playlist(playlist,soundtrack,cancel)
            # Use decoded playlist length for music-end exports (compressed metadata can include padding).
            if cfg.get('end_mode')=='music' or cfg.get('fit_music',False):
                actual_music=music_duration(soundtrack,cancel)
                try:plan=make_plan([item['info']['duration'] if item['video'] else None for item in items],actual_music,cfg)
                except TimingError as e:raise RenderError(str(e)) from e
                for item,position in zip(items,plan['items']):item.update(position)
                intro=plan['intro']/fps;seconds=plan['photo_seconds'];fade=min(.65,seconds/3)
                content_end=min(plan['content_cursor'],plan['fade_start']);fade_start=plan['fade_start']
                closing_frames=plan['closing'];closing_seconds=closing_frames/fps;count=plan['total'];total=count/fps
        master=Path(td)/'master.mp4'; cmd=[ff,'-hide_banner','-loglevel','error','-nostats','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w*2}x{h}','-r',str(fps),'-i','pipe:0']
        cmd+=['-t',str(total),'-vf','setsar=1','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(master)]
        with tempfile.TemporaryFile() as log:
            p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
            reader=None; current_item=-1; last_content_frame=None; subtitle=None
            try:
                blank=Image.new('RGB',(w*2,h),bg)
                # A blocked pipe write must not prevent the Cancel button from working.
                import threading
                finished=threading.Event()
                def watch_cancel():
                    while not finished.wait(.15):
                        if cancel.is_set():
                            if p.poll() is None: p.kill()
                            if reader is not None and reader.proc.poll() is None: reader.proc.kill()
                            return
                threading.Thread(target=watch_cancel,daemon=True).start()
                for n in range(count):
                    if cancel.is_set(): raise Cancelled()
                    t=n/fps
                    if t<intro:
                        frame=blank.copy()
                        if title is not None and t>=cfg['pause']:
                            tt=t-cfg['pause']; dur=cfg['title_seconds']; q=tt/dur
                            alpha=max(0,min(1,tt/1.0,(dur-tt)/1.0)); depth=q if cfg['title_motion']=='Approach' else math.sin(math.pi*q)
                            shift=round(w*.009*depth)
                            layer=title.copy(); layer.putalpha(layer.getchannel('A').point(lambda x:round(x*alpha)))
                            for j,x in enumerate([shift,-shift]): frame.paste(layer,(j*w+x,0),layer)
                    elif n<content_end:
                        while current_item+1<len(items) and n>=items[current_item+1]['start']:
                            if reader is not None:reader.close();reader=None
                            current_item+=1
                            item=items[current_item]
                            subtitle=caption_image(cfg.get('captions',{}).get(item['path'],''),w,h)
                            if item['video']:reader=VideoReader(item['path'],item['info'],w,h,fps,cfg)
                        i=current_item;item=items[i];local_frame=n-item['start'];st=local_frame/fps
                        if item['video']:
                            frame=reader.frame(allow_last=local_frame>=item['frames']-1)
                        else:
                            frame=scene(i,st)
                            if i>0 and not items[i-1]['video'] and st<fade: frame=Image.blend(scene(i-1,seconds),frame,st/fade)
                            if i==0 and st<fade: frame=Image.blend(blank,frame,st/fade)
                        if subtitle is not None:
                            caption_offset=[.006,.008,.010][cfg.get('layer_strength',1)] if cfg.get('depth_layers',True) else .002
                            shift=round(w*caption_offset) if cfg.get('caption_front',True) else 0
                            for eye,offset in enumerate([shift,-shift]):frame.paste(subtitle,(eye*w+offset,0),subtitle)
                        last_content_frame=frame.copy()
                    elif n<fade_start and last_content_frame is not None:
                        frame=last_content_frame
                    elif n<fade_start+closing_frames and last_content_frame is not None:
                        # Hold the ending composition as picture and soundtrack fade together.
                        amount=(n-fade_start+1)/closing_frames
                        frame=Image.blend(last_content_frame,Image.new('RGB',(w*2,h),'black'),amount)
                    else: frame=Image.new('RGB',(w*2,h),'black')
                    p.stdin.write(frame.tobytes())
                    if n%max(1,fps//4)==0: progress(int(n/count*85),f'Video built: {t:.1f} / {total:.1f} seconds • '+('closing fade' if n>=fade_start else 'holding final frame' if n>=content_end else 'opening title' if t<intro else (('video' if items[max(0,current_item)]['video'] else 'photo')+f' {current_item+1} of {len(items)}')))
                p.stdin.close()
                while p.poll() is None:
                    if cancel.wait(.2): raise Cancelled()
                if p.returncode: raise RuntimeError('Video encoder failed')
            except Exception as e:
                if p.poll() is None: p.kill()
                p.wait()
                if isinstance(e,Cancelled) or cancel.is_set(): raise Cancelled()
                raise RenderError(str(e) if isinstance(e,RenderError) else 'Rendering stopped unexpectedly. Your original files were not changed.',getattr(e,'details','')+'\n'+repr(e)+'\n'+log_tail(log)) from e
            finally:
                finished.set()
                if reader is not None: reader.close()
        audible=[item for item in items if item['video'] and item['info']['has_audio'] and cfg.get('video_sound',True) and item['path'] not in cfg.get('muted_videos',[])]
        if playlist or audible:
            progress(86,'Adding music and video sound')
            with_music=Path(td)/'with_music.mp4'
            acmd=[ff,'-hide_banner','-loglevel','error','-nostats','-y','-i',str(master)]
            filters=[];labels=[];idx=1
            if playlist:
                if cfg.get('end_mode','visuals')!='music' and not cfg.get('fit_music',False):acmd+=['-stream_loop','-1']
                acmd+=['-i',soundtrack]
                level='1'
                for item in audible:
                    level=f"if(between(t,{item['start']/fps},{(item['start']+item['frames'])/fps}),0.25,{level})"
                filters.append(f"[{idx}:a:0]asetpts=PTS-STARTPTS,atrim=duration={total},volume='{level}':eval=frame,afade=t=in:st=0:d=1.5[a{idx}]")
                labels.append(f'[a{idx}]');idx+=1
            for item in audible:
                acmd+=['-i',item['path']]
                delay=round(item['start']/fps*1000)
                filters.append(f"[{idx}:a:0]asetpts=PTS-STARTPTS,atrim=duration={item['frames']/fps},aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[a{idx}]")
                labels.append(f'[a{idx}]');idx+=1
            end_fade=f',afade=t=out:st={fade_start/fps}:d={closing_seconds}' if closing_frames else ''
            filters.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:normalize=0,alimiter=limit=0.95:latency=1,apad,atrim=duration={total}'+end_fade+'[sound]')
            run(acmd+['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[sound]','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(total),'-movflags','+faststart',str(with_music)],cancel)
            master=with_music
        from output_names import export_paths
        targets=export_paths(out,cfg.get('title',''),h,total)
        if cfg['sbs']:
            progress(87,'Saving undistorted full-SBS video')
            dest=targets['sbs']
            shutil.copyfile(master,dest); results.append(str(dest))
        if cfg.get('youtube',False):
            progress(88,'Applying YouTube metadata'); dest=targets['youtube']; part=Path(td)/'tagged.mkv'
            run([ff,'-y','-i',str(master),'-c','copy','-aspect',cfg.get('eye_aspect','16:9'),'-metadata:s:v:0','stereo_mode=1',str(part)],cancel)
            shutil.copyfile(part,dest); results.append(str(dest))
        if cfg['anaglyph']:
            progress(92,'Creating Dubois red/cyan anaglyph'); part=Path(td)/'anaglyph.mp4'; dest=targets['anaglyph']
            run([ff,'-y','-i',str(master),'-vf','stereo3d=sbsl:arcd,setsar=1','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(part)],cancel)
            shutil.copyfile(part,dest); results.append(str(dest))
    progress(100,'Finished'); return results
