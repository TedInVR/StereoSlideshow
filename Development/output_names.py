"""Portable, descriptive output names based on the finished timeline."""
import math,re,secrets
from pathlib import Path

def safe_title(title,limit=120):
    text=re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]+',' ',title or '')
    text=' '.join(text.split()).strip(' .')
    return text.encode('utf-8')[:limit].decode('utf-8',errors='ignore').rstrip(' .')

def duration_tag(seconds):
    whole=max(0,math.floor(seconds+.5));minutes,secs=divmod(whole,60)
    if not minutes:return f'{secs}sec'
    return f'{minutes}min'+(f'{secs:02}sec' if secs else '')

def export_paths(folder,title,height,seconds):
    folder=Path(folder);base=safe_title(title) or str(secrets.randbelow(90000000)+10000000)
    formats={'sbs':('Full_SBS_3D','mp4'),'anaglyph':('Anaglyph_3D','mp4'),'youtube':('YouTube_Full_SBS_3D','mkv')}
    take=1
    while True:
        prefix=base if take==1 else base+f'_{take}'
        results={key:folder/f'{prefix}_StereoSlideshow_{style}_{height}p_{duration_tag(seconds)}.{ext}' for key,(style,ext) in formats.items()}
        if not any(p.exists() for p in results.values()):return results
        take+=1
