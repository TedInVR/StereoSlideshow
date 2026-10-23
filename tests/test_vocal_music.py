import sys,tempfile,json,threading,io,wave
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from music_generator import *
base=dict(era='1950s',genre='Rock and roll',mood='Happy and upbeat',details='Piano and brass',voice='Female lead',language='English')
lyrics='[Verse 1]\nSummer days at Whalom Park\n[Chorus]\nKeep those happy memories'
provided=generation_request(dict(base,music_mode='lyrics',lyrics=lyrics),63)
assert provided['lyrics']==lyrics and 'Female lead vocals' in provided['prompt'] and 'no vocals' not in provided['prompt'] and not provided.get('sample_mode') and not provided['use_format']
topic=generation_request(dict(base,music_mode='topic',topic='Childhood visits to Whalom Park'),63)
assert topic['sample_mode'] and topic['thinking'] and topic['lyrics']=='' and 'Whalom Park' in topic['sample_query'] and 'instrumental' not in topic['sample_query'].lower()
assert generation_request(dict(base,music_mode='instrumental',lyrics=lyrics),63)['lyrics']=='[Instrumental]'
for options,seconds in [(dict(base,music_mode='topic',topic=''),63),(dict(base,music_mode='lyrics',lyrics=''),63),(dict(base,music_mode='lyrics',lyrics=lyrics),601)]:
 try:validate_music_options(options,seconds);raise AssertionError('Invalid song accepted')
 except MusicError:pass
buffer=io.BytesIO()
with wave.open(buffer,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\x00\x01'*24000*10)
audio=buffer.getvalue();requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,data):self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'code':200,'error':None,'data':data}).encode())
 def do_GET(self):
  if self.path=='/health':self.reply({'status':'ok','service':'ACE-Step API'})
  else:self.send_response(200);self.end_headers();self.wfile.write(audio)
 def do_POST(self):
  payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append((self.path,payload))
  if self.path=='/release_task':self.reply({'task_id':'song'})
  else:self.reply([{'task_id':'song','status':1,'result':json.dumps([{'file':'/v1/audio?path=song.wav','lyrics':lyrics}])}])
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);options=dict(base,music_mode='topic',topic='Whalom Park',url='http://127.0.0.1:'+str(server.server_port),logs=str(root/'Logs'))
  out=generate_soundtrack(options,3,root/'song.wav',threading.Event(),lambda x:None)
  meta=json.loads(Path(out).with_suffix('.json').read_text());assert meta['lyrics']==lyrics and meta['mode']=='topic';assert requests[0][1]['audio_duration']==10 and requests[0][1]['sample_mode']
  # Short vocal takes must not loop their words to fill a longer requested song.
  try:assemble([out],30,root/'bad.wav',threading.Event(),repeat=False);raise AssertionError('Short vocals looped')
  except MusicError as error:assert 'shorter' in str(error)
  folder=root/'ACE-Step-1.5';(folder/'acestep').mkdir(parents=True);(folder/'acestep/api_server.py').touch();(folder/'.venv/bin').mkdir(parents=True);python=folder/'.venv/bin/python';python.touch();python.chmod(0o755)
  fake_client=Mock();fake_client.url='http://127.0.0.1:8001';fake_client.health.side_effect=[MusicError('not started'),None]
  with patch('music_generator.subprocess.Popen') as popen:
   popen.return_value.poll.return_value=None;local=LocalServer();local.ensure(fake_client,str(folder),root/'Logs',threading.Event(),lambda x:None,need_lm=True)
   assert popen.call_args.kwargs['env']['ACESTEP_INIT_LLM']=='true';local.log.close();local.process=None
 print('Supplied lyrics unchanged, topic mode payload/returned lyrics, vocal preference/language, instrumental isolation, LM startup flag and no short-vocal looping passed.')
finally:server.shutdown();server.server_close()
