"""One frame-based timing calculation shared by preview and rendering."""
import math
class TimingError(ValueError):pass

def format_time(seconds):
    whole=int(round(seconds));hours,rest=divmod(whole,3600);minutes,secs=divmod(rest,60)
    clock=f'{hours}:{minutes:02}:{secs:02}' if hours else f'{minutes}:{secs:02}'
    number=f'{seconds:.2f}'.rstrip('0').rstrip('.')
    return f'{clock} ({number} seconds)'

def make_plan(durations,music_seconds,cfg):
    fps=cfg.get('fps',30);photo_seconds=cfg.get('seconds',5)
    intro=round((cfg.get('pause',1)+(cfg.get('title_seconds',6) if cfg.get('title','').strip() else 0))*fps)
    closing=max(0,round(cfg.get('closing_fade',6)*fps))
    video_frames=[None if d is None else max(1,math.ceil(d*fps)) for d in durations]
    photos=sum(d is None for d in durations);videos=sum(d is not None for d in durations)
    end_music=cfg.get('end_mode','visuals')=='music' or cfg.get('fit_music',False)
    counts=[max(1,round(photo_seconds*fps)) if d is None else d for d in video_frames]
    if end_music:
        if music_seconds is None or music_seconds<=0:raise TimingError('Add at least one readable music track to end with music.')
        total=round(music_seconds*fps);fade_start=total-closing
        if fade_start<=intro:raise TimingError('The music is shorter than the opening and closing fade. Use longer music or shorten those sections.')
        if cfg.get('fit_music',False):
            if not photos:raise TimingError('Automatic photo timing needs at least one photo. Use manual timing for a video-only sequence.')
            available=fade_start-intro-sum(v for v in video_frames if v is not None)
            if available<photos:raise TimingError('The music is too short for all the video clips, opening, closing fade, and photos. Add more music or shorten those sections.')
            base,remainder=divmod(available,photos);photo_index=0
            for i,d in enumerate(video_frames):
                if d is None:counts[i]=base+(photo_index<remainder);photo_index+=1
            photo_seconds=available/photos/fps
        tail=0
    else:
        fade_start=intro+sum(counts);tail=fps;total=fade_start+closing+tail
    cursor=intro;items=[]
    for count in counts:items.append({'start':cursor,'frames':int(count)});cursor+=count
    return dict(items=items,intro=intro,content_cursor=cursor,fade_start=fade_start,closing=closing,total=total,tail=tail,
                photo_seconds=photo_seconds,photo_count=photos,video_count=videos,video_seconds=sum(v for v in video_frames if v is not None)/fps,
                trims=end_music and cursor>fade_start,holds=end_music and cursor<fade_start,fps=fps)

def describe_plan(plan,music_seconds):
    f=plan['fps'];n=plan['photo_count'];lines=[]
    lines.append(f"{n} photos × {plan['photo_seconds']:.3f} seconds each; {plan['video_count']} video clips = {format_time(plan['video_seconds'])}")
    lines.append(f"Opening: {format_time(plan['intro']/f)} · Closing fade: {format_time(plan['closing']/f)}")
    if music_seconds is not None:lines.append('Music playlist: '+format_time(music_seconds))
    lines.append('Finished video: '+format_time(plan['total']/f))
    if plan['trims']:lines.append('Music ends first: later photos/clips may be cut short or omitted. Fit photo timing avoids this when all clips fit.')
    if plan['holds']:lines.append('Visuals finish first: the final displayed frame holds until the closing fade.')
    if plan['tail']:lines.append('Includes the final one-second black tail. Music repeats if needed.')
    if n and plan['photo_seconds']*f%1:lines.append('Photo times may differ by one video frame to match the music exactly.')
    return '\n'.join(lines)
