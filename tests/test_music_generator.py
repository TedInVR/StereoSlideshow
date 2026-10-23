import sys, tempfile, threading, json, wave, io, math, struct
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from music_generator import *
record=[];state={'mode':'success','queries':0}
buffer=io.BytesIO()
with wave.open(buffer,'wb') as wav:
 wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(i*.1))) for i in range(24000)))
audio=buffer.getvalue()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,data):
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps({'code':200,'data':data,'error':None}).encode())
 def do_GET(self):
  if self.path=='/health':self.reply({'status':'ok','service':'ACE-Step API'})
  else:self.send_response(200);self.end_headers();self.wfile.write(audio)
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));record.append((self.path,data))
  if self.path=='/release_task':self.reply({'task_id':'test','status':'queued'})
  else:
   status={'success':1,'failed':2,'pending':0}[state['mode']];self.reply([{'task_id':'test','status':status,'result':json.dumps([{'file':'/v1/audio?path=generated.wav'}])}])
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);url='http://127.0.0.1:'+str(server.server_port);options=dict(url=url,folder='',era='1950s',genre='Rock and roll',mood='Happy and upbeat',details='piano',logs=str(root/'Logs'));cancel=threading.Event()
  output=generate_soundtrack(options,3,root/'music.wav',cancel,lambda x:None)
  import subprocess
  info=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_streams','-of','json',output]))['streams'][0]
  assert int(info['duration_ts'])==3*48000 and info['channels']==2 and info['bits_per_sample']==24
  request=record[0][1];assert request['audio_duration']==10 and request['batch_size']==1 and request['lyrics']=='[Instrumental]' and request['use_random_seed']
  assert '1950s' in request['prompt'] and 'rock and roll' in request['prompt']
  assert json.loads((root/'music.json').read_text())['requested_seconds']==3
  # A long timeline uses bounded sections, then a sample-exact crossfade join.
  lengths=section_lengths(601.25);assert len(lengths)==2 and abs(sum(lengths)-2-601.25)<1e-9 and max(lengths)<=600
  sample=root/'sample.wav';sample.write_bytes(audio);assemble([sample,sample],601.25,root/'long.wav',cancel)
  duration=float(subprocess.check_output(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',str(root/'long.wav')]))
  assert abs(duration-601.25)<1/48000
  for seconds in [1,10,600,600.01,1198,1200,3600]:
   parts=section_lengths(seconds);assert all(10<=x<=600 for x in parts)
  state['mode']='failed'
  try:AceClient(url).generate('test',10,cancel,lambda x:None);raise AssertionError('failure ignored')
  except MusicError:pass
  state['mode']='pending';timer=threading.Timer(.1,cancel.set);timer.start()
  try:AceClient(url).generate('test',10,cancel,lambda x:None);raise AssertionError('cancellation ignored')
  except MusicCancelled:pass
  timer.join()
  for bad in ['https://example.com','http://127.0.0.1.evil.com:8001','http://user:pass@localhost:8001','file:///tmp/music','http://localhost:8001/path']:
   try:local_url(bad);raise AssertionError(bad)
   except MusicError:pass
  folder=root/'ACE-Step-1.5';(folder/'acestep').mkdir(parents=True);(folder/'acestep/api_server.py').touch();(folder/'.venv/bin').mkdir(parents=True);python=folder/'.venv/bin/python';python.touch();python.chmod(0o755)
  install,cmd=launch_command(str(folder),8001);assert cmd[1:]==['-m','acestep.api_server','--host','127.0.0.1','--port','8001']
 print('ACE REST generation/download, exact stereo WAV duration, long-section crossfade, failure/cancellation, local URL and installed-runtime selection passed.')
finally:server.shutdown();server.server_close()
