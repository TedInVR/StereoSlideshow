import sys,tempfile,subprocess,threading,json,math
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from timing import make_plan,TimingError,format_time
from engine import render
cfg=dict(fps=30,seconds=5,pause=1,title='Title',title_seconds=6,closing_fade=6,end_mode='music',fit_music=True)
p=make_plan([None]*34,243,cfg);assert abs(p['photo_seconds']-(243-1-6-6)/34)<.001;assert p['total']==243*30
assert p['items'][-1]['start']+p['items'][-1]['frames']==p['fade_start'];assert max(x['frames'] for x in p['items'])-min(x['frames'] for x in p['items'])<=1
p=make_plan([None,30,None],100,cfg);assert abs(p['photo_seconds']-28.5)<.001
try:make_plan([None,300,None],100,cfg)
except TimingError:pass
else:raise AssertionError('Impossible fit not rejected')
assert format_time(243)=='4:03 (243 seconds)'
with tempfile.TemporaryDirectory() as td:
 root=Path(td);im=root/'odd_photo.png';Image.new('RGB',(201,100),'teal').save(im)
 tracks=[]
 for n,hz in enumerate([440,880]):
  f=root/f'track{n}.wav';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={hz}:duration=2',str(f)],check=True);tracks.append(str(f))
 base=dict(width=320,height=120,fps=15,seconds=1,pause=0,title_seconds=3,title='',title_motion='Approach',background='#000000',text_color='#ffffff',cross=False,sbs=True,anaglyph=True,closing_fade=.5,end_mode='music',fit_music=True)
 files=render([str(im)]*3,tracks,root/'fit',base,lambda *x:None,threading.Event())
 for file in files:
  data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',file]));assert abs(float(data['format']['duration'])-4)<.08
  subprocess.run(['ffmpeg','-v','error','-i',file,'-f','null','-'],check=True)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',files[0],'-vn','-ac','1','-ar','16000','-f','f32le','-']);x=np.frombuffer(raw,dtype='<f4')
 def amp(t,hz):
  y=x[int(t*16000):int((t+.25)*16000)];return abs(np.dot(y,np.exp(-2j*np.pi*hz*np.arange(len(y))/16000)))
 assert amp(1.7,440)>amp(1.7,880)*20
 assert amp(2.5,880)>amp(2.5,440)*20
 # Longer visual sequence repeats the whole ordered playlist, not each track separately.
 base.update(end_mode='visuals',fit_music=False,seconds=6,closing_fade=0,anaglyph=False)
 f=render([str(im)],tracks,root/'loop',base,lambda *x:None,threading.Event())[0]
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',f,'-vn','-ac','1','-ar','16000','-f','f32le','-']);x=np.frombuffer(raw,dtype='<f4')
 assert amp(4.5,440)>amp(4.5,880)*20
 # Music-end manual timing can hold or trim visuals to the track end.
 base.update(end_mode='music',seconds=1,closing_fade=.5)
 f=render([str(im)],tracks,root/'hold',base,lambda *x:None,threading.Event())[0]
 assert abs(float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',f]))['format']['duration'])-4)<.08
 base.update(seconds=20)
 f=render([str(im)],tracks,root/'trim',base,lambda *x:None,threading.Event())[0]
 assert abs(float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',f]))['format']['duration'])-4)<.08
print('Frame-exact fit, title/clip/fade overhead, impossible budgets, ordered soundtrack, whole-playlist looping, music-end hold/trim, odd-width photos, and both exports passed.')
