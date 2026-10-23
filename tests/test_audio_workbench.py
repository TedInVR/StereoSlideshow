"""Real FFmpeg preservation checks; AI calls are simulated, not model inference."""
import hashlib,json,subprocess,sys,tempfile,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import audio_workbench as a
from music_generator import MusicCancelled,MusicError
from engine import binary,music_duration
cancel=threading.Event()
def pcm(path):return subprocess.check_output([binary('ffmpeg'),'-v','error','-i',str(path),'-f','s24le','-c:a','pcm_s24le','-'])
def tone(path,hz,seconds):subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i',f'sine=frequency={hz}:sample_rate=48000:duration={seconds}','-ac','2','-c:a','pcm_s24le',str(path)],check=True)
def same_outside(source,result,lo,hi):
 x,y=pcm(source),pcm(result);assert len(x)==len(y);assert x[:round(lo*48000)*6]==y[:round(lo*48000)*6];assert x[round(hi*48000)*6:]==y[round(hi*48000)*6:];assert x!=y
with tempfile.TemporaryDirectory() as td:
 root=Path(td);source=root/'My recording.wav';tone(source,220,4);original=source.read_bytes();lyrics='[Verse]\nMy original words'
 source.with_suffix('.json').write_text(json.dumps({'style':{'details':'Warm piano','music_mode':'lyrics','lyrics':lyrics},'mode':'lyrics','lyrics':lyrics}))
 imported=Path(a.import_take(source,root/'takes',cancel));assert imported.read_bytes()==original and a.take_style(a.metadata_for(imported))['lyrics']==lyrics
 for suffix in ('.wav','.flac','.mp3'):
  dest=root/('Export'+suffix);a.export_take(imported,dest,cancel);assert dest.is_file() and abs(music_duration(dest,cancel)-4)<.1;assert a.metadata_for(dest)['lyrics']==lyrics
 assert (root/'Export.wav').read_bytes()==original
 cancelled=threading.Event();cancelled.set()
 try:a.export_take(imported,root/'Cancelled.wav',cancelled);raise AssertionError('Cancellation ignored')
 except MusicCancelled:assert not (root/'Cancelled.wav').exists()
 requests=[]
 class Client:
  def __init__(self,*args):pass
  def request(self,*args):return {'models':[{'name':a.BASE_MODEL}]}
  def generate(self,prompt,seconds,event,status,payload=None,result_info=None):
   requests.append(payload);assert Path(payload['src_audio_path']).is_file();return str(seconds)
  def download(self,url,path,event):tone(path,880,float(url))
 class Server:
  def ensure(self,*args,**kwargs):pass
  def stop(self):pass
 options=dict(era='Any era',genre='Jazz',mood='Warm and nostalgic',music_mode='lyrics',voice='No preference',language='English',lyrics=lyrics,source_audio=str(imported),logs=str(root),edit_start=1,edit_end=3)
 with patch.object(a,'AceClient',Client),patch.object(a,'LocalServer',Server):
  result=root/'repaint.wav';a.edit_soundtrack(dict(options,operation='repaint'),4,result,cancel,lambda x:None);same_outside(imported,result,1,3);assert requests[-1]['task_type']=='repaint' and requests[-1]['chunk_mask_mode']=='explicit'
  result=root/'extended.wav';a.edit_soundtrack(dict(options,operation='extend',lyrics='[Outro]\nNew ending'),6,result,cancel,lambda x:None)
  assert abs(music_duration(result,cancel)-6)<.001 and pcm(imported)[:int(3.5*48000)*6]==pcm(result)[:int(3.5*48000)*6];assert 'My original words' in a.metadata_for(result)['lyrics'] and 'New ending' in a.metadata_for(result)['lyrics'];assert requests[-1]['repainting_start']==3.5
  result=root/'mixed.wav';a.edit_soundtrack(dict(options,operation='layer',instrument='Guitar',layer_volume=35),4,result,cancel,lambda x:None)
  assert abs(music_duration(result,cancel)-4)<.001 and requests[-1]['task_type']=='lego' and requests[-1]['model']==a.BASE_MODEL and requests[-1]['track_name']=='guitar';assert result.with_name('mixed - instrument.wav').exists();assert a.metadata_for(result)['lyrics']==lyrics
  class WrongModel(Client):
   def request(self,*args):return {'models':[{'name':'acestep-v15-turbo'}]}
  with patch.object(a,'AceClient',WrongModel):
   try:a.edit_soundtrack(dict(options,operation='layer',instrument='Guitar'),4,root/'wrong.wav',cancel,lambda x:None);raise AssertionError('Wrong model accepted')
   except MusicError as error:assert 'Base' in str(error) and not (root/'wrong.wav').exists()
 result=root/'trim.wav';a.edit_soundtrack(dict(options,operation='trim'),2,result,cancel,lambda x:None);assert pcm(result)==pcm(imported)[:2*48000*6]
 assert source.read_bytes()==original and imported.read_bytes()==original
 assert all('.partial.' not in p.name for p in root.rglob('*'))
 assert a.take_style({'mode':'topic','lyrics':'Words','prompt':'Old style'})['music_mode']=='lyrics'
print('Audio import/export, sidecar recovery, cancellation, exact PCM preservation outside edits, extension joins, trim, instrument mixing/stem retention and Base-model guard passed (AI responses simulated).')
